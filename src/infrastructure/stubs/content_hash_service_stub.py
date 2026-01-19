"""Content hash service stub implementation (Story 0.5, AC3).

This module provides an in-memory stub implementation of
ContentHashServiceProtocol for development and testing purposes.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → Deterministic hashing
- CT-12: Witnessing creates accountability → Track hash operations
- HP-2: Content hashing service for duplicate detection
- HC-5: Sybil amplification defense via content hash

Testing Features:
- Deterministic fake hashes (using hashlib.sha256 as fallback)
- Operation tracking for assertions
- Configurable hash overrides for specific inputs
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

from src.application.ports.content_hash_service import ContentHashServiceProtocol


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class HashOperation:
    """Record of a hash operation for test assertions.

    Attributes:
        content: The content that was hashed (bytes)
        result: The hash result (32 bytes)
        timestamp: When the operation occurred
        method: Which method was called (hash_content, hash_text, verify_hash)
    """

    content: bytes
    result: bytes
    timestamp: datetime
    method: str


class ContentHashServiceStub(ContentHashServiceProtocol):
    """In-memory stub implementation of ContentHashServiceProtocol.

    This stub provides deterministic hashing for testing without requiring
    the blake3 library. Uses SHA-256 truncated to 32 bytes as a fallback.

    NOT suitable for production use.

    Constitutional Compliance:
    - HP-2: Duplicate detection (simulated with SHA-256)
    - HC-5: Sybil amplification defense testing

    Testing Features:
    - Track all hash operations
    - Configure specific content -> hash mappings
    - Verify hash operation counts and parameters

    Attributes:
        HASH_SIZE: Fixed output size in bytes (32)
        _operations: List of HashOperation records
        _overrides: Dictionary of content -> hash overrides
    """

    HASH_SIZE: int = 32

    def __init__(self) -> None:
        """Initialize the stub with empty state."""
        self._operations: list[HashOperation] = []
        self._overrides: dict[bytes, bytes] = {}
        self._verify_operations: list[tuple[bytes, bytes, bool]] = []

    def hash_content(self, content: bytes) -> bytes:
        """Hash raw bytes content to 32-byte digest.

        Uses configured override if available, otherwise SHA-256.

        Args:
            content: Raw bytes to hash

        Returns:
            32-byte hash digest
        """
        # Check for configured override
        if content in self._overrides:
            result = self._overrides[content]
        else:
            # Use SHA-256 as deterministic fallback (already 32 bytes)
            result = hashlib.sha256(content).digest()

        # Record operation
        self._operations.append(
            HashOperation(
                content=content,
                result=result,
                timestamp=_utc_now(),
                method="hash_content",
            )
        )

        return result

    def hash_text(self, text: str) -> bytes:
        """Hash string content to 32-byte digest.

        Encodes string as UTF-8 before hashing.

        Args:
            text: String content to hash

        Returns:
            32-byte hash digest
        """
        content = text.encode("utf-8")

        # Check for configured override
        if content in self._overrides:
            result = self._overrides[content]
        else:
            result = hashlib.sha256(content).digest()

        # Record operation
        self._operations.append(
            HashOperation(
                content=content,
                result=result,
                timestamp=_utc_now(),
                method="hash_text",
            )
        )

        return result

    def verify_hash(self, content: bytes, expected_hash: bytes) -> bool:
        """Verify that content matches the expected hash.

        Performs constant-time comparison.

        Args:
            content: Raw bytes content to verify
            expected_hash: Expected 32-byte hash

        Returns:
            True if content hash matches expected_hash

        Raises:
            ValueError: If expected_hash is not 32 bytes
        """
        if len(expected_hash) != self.HASH_SIZE:
            raise ValueError(
                f"Expected hash must be {self.HASH_SIZE} bytes, got {len(expected_hash)}"
            )

        actual_hash = self.hash_content(content)
        result = hmac.compare_digest(actual_hash, expected_hash)

        # Record verify operation
        self._verify_operations.append((content, expected_hash, result))

        return result

    # Testing helper methods

    def clear(self) -> None:
        """Clear all recorded operations and overrides."""
        self._operations.clear()
        self._overrides.clear()
        self._verify_operations.clear()

    def set_override(self, content: bytes, hash_result: bytes) -> None:
        """Configure a specific hash result for given content.

        Useful for testing specific hash values.

        Args:
            content: The content bytes
            hash_result: The hash result to return (must be 32 bytes)

        Raises:
            ValueError: If hash_result is not 32 bytes
        """
        if len(hash_result) != self.HASH_SIZE:
            raise ValueError(
                f"Hash result must be {self.HASH_SIZE} bytes, got {len(hash_result)}"
            )
        self._overrides[content] = hash_result

    def set_text_override(self, text: str, hash_result: bytes) -> None:
        """Configure a specific hash result for given text content.

        Convenience method for string content.

        Args:
            text: The text content
            hash_result: The hash result to return (must be 32 bytes)
        """
        self.set_override(text.encode("utf-8"), hash_result)

    def get_operations(self) -> list[HashOperation]:
        """Get list of all hash operations."""
        return self._operations.copy()

    def get_operation_count(self) -> int:
        """Get count of hash operations."""
        return len(self._operations)

    def get_hash_content_calls(self) -> list[HashOperation]:
        """Get operations from hash_content() calls."""
        return [op for op in self._operations if op.method == "hash_content"]

    def get_hash_text_calls(self) -> list[HashOperation]:
        """Get operations from hash_text() calls."""
        return [op for op in self._operations if op.method == "hash_text"]

    def get_verify_calls(self) -> list[tuple[bytes, bytes, bool]]:
        """Get list of verify_hash() calls as (content, expected, result) tuples."""
        return self._verify_operations.copy()

    def was_content_hashed(self, content: bytes) -> bool:
        """Check if specific content was ever hashed."""
        return any(op.content == content for op in self._operations)

    def was_text_hashed(self, text: str) -> bool:
        """Check if specific text was ever hashed."""
        return self.was_content_hashed(text.encode("utf-8"))

    def get_last_hash(self) -> bytes | None:
        """Get the result of the most recent hash operation."""
        if not self._operations:
            return None
        return self._operations[-1].result
