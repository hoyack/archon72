"""Hash algorithm implementations for governance event chain.

Story: consent-gov-1.3: Hash Chain Implementation

This module provides hash algorithm implementations for the consent-based
governance event ledger. Both BLAKE3 (preferred) and SHA-256 (baseline)
are supported per AD-6.

Algorithm Selection (Locked per governance-architecture.md):
| Algorithm | Status             | Use                              |
|-----------|--------------------|----------------------------------|
| BLAKE3    | Preferred          | High-throughput ledger operations|
| SHA-256   | Required baseline  | Portability, existing patterns   |

Hash Format (Locked):
    blake3:abc123def456...
    sha256:789xyz012abc...

Constitutional Constraints:
- AD-6: BLAKE3/SHA-256 hash algorithms
- NFR-CONST-02: Event integrity verification
- NFR-AUDIT-06: Deterministic replay

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Hash Chain Implementation (Locked)]
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass

# Import blake3 lazily to avoid import error if not installed
try:
    import blake3 as _blake3_lib

    _BLAKE3_AVAILABLE = True
except ImportError:
    _BLAKE3_AVAILABLE = False


# Genesis hash constant (prev_hash for first event in chain)
# 64 zeros as hex-encoded 32-byte hash
GENESIS_PREV_HASH = "blake3:0000000000000000000000000000000000000000000000000000000000000000"

# Default algorithm for new events
DEFAULT_ALGORITHM = "blake3"

# Supported algorithms registry
SUPPORTED_ALGORITHMS = frozenset({"blake3", "sha256"})


@runtime_checkable
class HashAlgorithm(Protocol):
    """Protocol for hash algorithm implementations.

    Per AD-6, all hash algorithms must:
    - Have a name property for the algorithm prefix
    - Implement hash() returning bytes
    - Support verification by extracting prefix from hash string
    """

    @property
    def name(self) -> str:
        """Algorithm name for prefix (e.g., 'blake3', 'sha256')."""
        ...

    def hash(self, data: bytes) -> bytes:
        """Compute hash of data.

        Args:
            data: The bytes to hash.

        Returns:
            Hash digest as bytes (32 bytes for both BLAKE3 and SHA-256).
        """
        ...


class Blake3Hasher:
    """BLAKE3 hash implementation (preferred per AD-6).

    BLAKE3 is the preferred algorithm for high-throughput ledger operations
    due to its superior performance characteristics while maintaining
    cryptographic security.

    Hash output: 32 bytes (256 bits), hex-encoded to 64 characters.
    """

    @property
    def name(self) -> str:
        """Return algorithm name for prefix."""
        return "blake3"

    def hash(self, data: bytes) -> bytes:
        """Compute BLAKE3 hash of data.

        Args:
            data: The bytes to hash.

        Returns:
            32-byte BLAKE3 digest.

        Raises:
            RuntimeError: If blake3 library is not available.
        """
        if not _BLAKE3_AVAILABLE:
            raise RuntimeError(
                "BLAKE3 library not available. Install with: pip install blake3"
            )
        return _blake3_lib.blake3(data).digest()


class Sha256Hasher:
    """SHA-256 hash implementation (required baseline per AD-6).

    SHA-256 is the required baseline algorithm for portability and
    compatibility with existing patterns (commit-reveal, etc.).

    Hash output: 32 bytes (256 bits), hex-encoded to 64 characters.
    """

    @property
    def name(self) -> str:
        """Return algorithm name for prefix."""
        return "sha256"

    def hash(self, data: bytes) -> bytes:
        """Compute SHA-256 hash of data.

        Args:
            data: The bytes to hash.

        Returns:
            32-byte SHA-256 digest.
        """
        return hashlib.sha256(data).digest()


# Hasher instances for reuse
_BLAKE3_HASHER = Blake3Hasher()
_SHA256_HASHER = Sha256Hasher()

# Hasher registry for algorithm selection
_HASHERS: dict[str, HashAlgorithm] = {
    "blake3": _BLAKE3_HASHER,
    "sha256": _SHA256_HASHER,
}


def get_hasher(algorithm: str) -> HashAlgorithm:
    """Get a hasher instance for the specified algorithm.

    Args:
        algorithm: Algorithm name ('blake3' or 'sha256').

    Returns:
        HashAlgorithm instance.

    Raises:
        ValueError: If algorithm is not supported.
    """
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported hash algorithm: {algorithm!r}. "
            f"Supported algorithms: {', '.join(sorted(SUPPORTED_ALGORITHMS))}"
        )
    return _HASHERS[algorithm]


def extract_algorithm_from_hash(prefixed_hash: str) -> str:
    """Extract algorithm name from prefixed hash string.

    Hash format: {algorithm}:{hex_digest}
    Example: blake3:abc123...

    Args:
        prefixed_hash: Hash string with algorithm prefix.

    Returns:
        Algorithm name (e.g., 'blake3', 'sha256').

    Raises:
        ValueError: If hash format is invalid or algorithm unsupported.
    """
    if ":" not in prefixed_hash:
        raise ValueError(
            f"Invalid hash format: {prefixed_hash!r}. "
            f"Expected format: algorithm:hex_digest"
        )

    algorithm, _hex_digest = prefixed_hash.split(":", 1)

    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported hash algorithm in prefix: {algorithm!r}. "
            f"Supported algorithms: {', '.join(sorted(SUPPORTED_ALGORITHMS))}"
        )

    return algorithm


def extract_hex_digest(prefixed_hash: str) -> str:
    """Extract hex digest from prefixed hash string.

    Hash format: {algorithm}:{hex_digest}
    Example: blake3:abc123...

    Args:
        prefixed_hash: Hash string with algorithm prefix.

    Returns:
        Hex digest without algorithm prefix.

    Raises:
        ValueError: If hash format is invalid.
    """
    if ":" not in prefixed_hash:
        raise ValueError(
            f"Invalid hash format: {prefixed_hash!r}. "
            f"Expected format: algorithm:hex_digest"
        )

    _algorithm, hex_digest = prefixed_hash.split(":", 1)
    return hex_digest


def compute_hash(data: bytes, algorithm: str = DEFAULT_ALGORITHM) -> str:
    """Compute hash of data with algorithm prefix.

    Args:
        data: The bytes to hash.
        algorithm: Algorithm name (default: 'blake3').

    Returns:
        Prefixed hash string (e.g., 'blake3:abc123...').

    Raises:
        ValueError: If algorithm is not supported.
    """
    hasher = get_hasher(algorithm)
    digest = hasher.hash(data)
    return f"{algorithm}:{digest.hex()}"


def verify_hash(data: bytes, prefixed_hash: str) -> bool:
    """Verify that data produces the expected hash.

    The algorithm is extracted from the hash prefix, allowing verification
    of hashes created with either BLAKE3 or SHA-256.

    Args:
        data: The bytes to verify.
        prefixed_hash: Expected hash with algorithm prefix.

    Returns:
        True if hash matches, False otherwise.

    Raises:
        ValueError: If hash format is invalid or algorithm unsupported.
    """
    algorithm = extract_algorithm_from_hash(prefixed_hash)
    expected_hex = extract_hex_digest(prefixed_hash)

    hasher = get_hasher(algorithm)
    actual_digest = hasher.hash(data)

    return actual_digest.hex() == expected_hex


def is_genesis_hash(prefixed_hash: str) -> bool:
    """Check if hash is the genesis (null) hash.

    Args:
        prefixed_hash: Hash string with algorithm prefix.

    Returns:
        True if this is a genesis hash (all zeros).
    """
    try:
        hex_digest = extract_hex_digest(prefixed_hash)
        return hex_digest == "0" * 64
    except ValueError:
        return False


def make_genesis_hash(algorithm: str = DEFAULT_ALGORITHM) -> str:
    """Create a genesis (null) hash for the specified algorithm.

    Args:
        algorithm: Algorithm name (default: 'blake3').

    Returns:
        Genesis hash with algorithm prefix (all zeros).

    Raises:
        ValueError: If algorithm is not supported.
    """
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported hash algorithm: {algorithm!r}. "
            f"Supported algorithms: {', '.join(sorted(SUPPORTED_ALGORITHMS))}"
        )
    return f"{algorithm}:{'0' * 64}"


def validate_hash_format(prefixed_hash: str) -> bool:
    """Validate that a hash string has the correct format.

    Hash format requirements:
    - Contains exactly one colon separator
    - Algorithm prefix is supported (blake3 or sha256)
    - Hex digest is exactly 64 lowercase hexadecimal characters

    Args:
        prefixed_hash: Hash string to validate.

    Returns:
        True if format is valid, False otherwise.
    """
    try:
        if ":" not in prefixed_hash:
            return False

        algorithm, hex_digest = prefixed_hash.split(":", 1)

        if algorithm not in SUPPORTED_ALGORITHMS:
            return False

        if len(hex_digest) != 64:
            return False

        # Check if hex_digest is valid lowercase hexadecimal
        int(hex_digest, 16)
        if hex_digest != hex_digest.lower():
            return False

        return True
    except (ValueError, AttributeError):
        return False
