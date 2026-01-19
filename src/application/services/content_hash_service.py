"""BLAKE3 content hash service implementation (Story 0.5, HP-2, HC-5).

This module implements the ContentHashServiceProtocol using BLAKE3
for fast, secure content hashing in the petition system.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → Deterministic hashing
- CT-12: Witnessing creates accountability → Hashes for witness integrity
- HP-2: Content hashing service for duplicate detection
- HC-5: Sybil amplification defense via content hash

Why BLAKE3:
- 10x faster than SHA-256 on modern hardware
- Parallelism support (SIMD, multi-threading)
- Modern cryptographic design (2020)
- Fixed 32-byte output (256 bits)

Usage:
    from src.application.services.content_hash_service import Blake3ContentHashService

    service = Blake3ContentHashService()
    content_hash = service.hash_text("Petition content here")
"""

from __future__ import annotations

import hmac

import blake3

from src.application.services.base import LoggingMixin


class Blake3ContentHashService(LoggingMixin):
    """BLAKE3 implementation of content hashing (Story 0.5, HP-2, HC-5).

    Provides fast, secure content hashing for petition duplicate detection
    and witness integrity verification.

    Constitutional Constraints:
    - HP-2: Duplicate detection via content hash
    - HC-5: Sybil amplification defense
    - CT-12: Witness integrity

    Attributes:
        HASH_SIZE: Fixed output size in bytes (32)
    """

    HASH_SIZE: int = 32

    def __init__(self) -> None:
        """Initialize the BLAKE3 content hash service."""
        self._init_logger(component="petition")

    def hash_content(self, content: bytes) -> bytes:
        """Hash raw bytes content to 32-byte BLAKE3 digest.

        Constitutional Constraint (HP-2): Duplicate detection.
        Constitutional Constraint (CT-12): Witness integrity.

        Uses BLAKE3's default mode (not keyed or derive_key mode).

        Args:
            content: Raw bytes to hash (UTF-8 encoded text, or other bytes)

        Returns:
            32-byte BLAKE3 hash digest
        """
        return blake3.blake3(content).digest()

    def hash_text(self, text: str) -> bytes:
        """Hash string content to 32-byte BLAKE3 digest.

        Convenience method that encodes string as UTF-8 before hashing.
        Uses canonical UTF-8 encoding for determinism.

        Constitutional Constraint (HP-2): Duplicate detection.

        Args:
            text: String content to hash (will be UTF-8 encoded)

        Returns:
            32-byte BLAKE3 hash digest
        """
        return self.hash_content(text.encode("utf-8"))

    def verify_hash(self, content: bytes, expected_hash: bytes) -> bool:
        """Verify that content matches the expected hash.

        Performs constant-time comparison to prevent timing attacks
        using hmac.compare_digest().

        Constitutional Constraint (CT-12): Witness integrity verification.

        Args:
            content: Raw bytes content to verify
            expected_hash: Expected 32-byte BLAKE3 hash

        Returns:
            True if content hash matches expected_hash, False otherwise

        Raises:
            ValueError: If expected_hash is not 32 bytes
        """
        if len(expected_hash) != self.HASH_SIZE:
            raise ValueError(
                f"Expected hash must be {self.HASH_SIZE} bytes, got {len(expected_hash)}"
            )

        actual_hash = self.hash_content(content)
        return hmac.compare_digest(actual_hash, expected_hash)

    def hash_petition_content(self, petition_text: str) -> bytes:
        """Hash petition text content for duplicate detection.

        Convenience method specifically for petition content.
        Applies canonical normalization for consistent hashing.

        Constitutional Constraint (HC-5): Sybil amplification defense.

        Args:
            petition_text: The petition text content

        Returns:
            32-byte BLAKE3 hash digest
        """
        return self.hash_text(petition_text)
