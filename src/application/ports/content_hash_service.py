"""Content hash service port for petition integrity (Story 0.5, HP-2).

This module defines the abstract interface for content hashing operations
in the Three Fates petition system.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → Hashes must be deterministic
- CT-12: Witnessing creates accountability → Hashes used for witness integrity
- HP-2: Content hashing service for duplicate detection
- HC-5: Duplicate detection via content hash (Sybil amplification defense)

Developer Golden Rules:
1. DETERMINISM - Same input always produces same output
2. 32 BYTES - All hashes are exactly 32 bytes (256 bits)
3. UTF-8 - Text content uses UTF-8 encoding
4. NO SECRETS - Hashes are not keyed/secret by default
"""

from __future__ import annotations

from typing import Protocol


class ContentHashServiceProtocol(Protocol):
    """Protocol for content hashing operations (Story 0.5, HP-2, HC-5).

    Defines the contract for hashing petition content for duplicate detection
    and witness integrity. Implementations use BLAKE3 for speed and security.

    Constitutional Constraints:
    - HP-2: Content hashing for duplicate detection
    - HC-5: Sybil amplification defense via content hash index
    - CT-12: Hash used in witnessing pipeline

    Why BLAKE3:
    - 10x faster than SHA-256 on modern hardware
    - Parallelism support (SIMD, multi-threading)
    - Modern cryptographic design (2020)
    - Fixed 32-byte output (256 bits)

    Methods:
        hash_content: Hash raw bytes to 32-byte digest
        hash_text: Convenience method for string content
        verify_hash: Verify content matches expected hash
    """

    def hash_content(self, content: bytes) -> bytes:
        """Hash raw bytes content to 32-byte BLAKE3 digest.

        Constitutional Constraint (HP-2): Duplicate detection.
        Constitutional Constraint (CT-12): Witness integrity.

        Args:
            content: Raw bytes to hash (UTF-8 encoded text, or other bytes)

        Returns:
            32-byte BLAKE3 hash digest

        Example:
            >>> service = Blake3ContentHashService()
            >>> digest = service.hash_content(b"Hello, World!")
            >>> len(digest)
            32
        """
        ...

    def hash_text(self, text: str) -> bytes:
        """Hash string content to 32-byte BLAKE3 digest.

        Convenience method that encodes string as UTF-8 before hashing.
        Uses canonical UTF-8 encoding for determinism.

        Constitutional Constraint (HP-2): Duplicate detection.

        Args:
            text: String content to hash (will be UTF-8 encoded)

        Returns:
            32-byte BLAKE3 hash digest

        Example:
            >>> service = Blake3ContentHashService()
            >>> digest = service.hash_text("Hello, World!")
            >>> len(digest)
            32
        """
        ...

    def verify_hash(self, content: bytes, expected_hash: bytes) -> bool:
        """Verify that content matches the expected hash.

        Performs constant-time comparison to prevent timing attacks.

        Constitutional Constraint (CT-12): Witness integrity verification.

        Args:
            content: Raw bytes content to verify
            expected_hash: Expected 32-byte BLAKE3 hash

        Returns:
            True if content hash matches expected_hash, False otherwise

        Raises:
            ValueError: If expected_hash is not 32 bytes

        Example:
            >>> service = Blake3ContentHashService()
            >>> content = b"Hello, World!"
            >>> hash_digest = service.hash_content(content)
            >>> service.verify_hash(content, hash_digest)
            True
        """
        ...
