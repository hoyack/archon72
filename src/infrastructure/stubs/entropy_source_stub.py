"""Entropy source stub for development and testing (FR61).

Provides a deterministic entropy source for testing witness selection.

WARNING: This stub is NOT for production use.
Production implementations should use real external entropy sources
like drand.cloudflare.com or random.org.

Constitutional Constraints:
- FR61: External entropy source required
- NFR57: Halt on entropy failure (not weak randomness)
"""

from __future__ import annotations

import hashlib
import os
import warnings

from src.application.ports.entropy_source import EntropySourceProtocol
from src.domain.errors.witness_selection import EntropyUnavailableError

# DEV MODE warning prefix
DEV_MODE_WARNING = "[DEV MODE] EntropySourceStub in use - NOT FOR PRODUCTION"


class EntropySourceStub(EntropySourceProtocol):
    """Stub implementation of EntropySourceProtocol for testing.

    Provides deterministic or configurable entropy for testing
    witness selection behavior without external dependencies.

    WARNING: This implementation uses predictable entropy and
    should NEVER be used in production environments.

    Features:
    - Configurable entropy for controlled testing
    - Failure simulation for error path testing
    - DEV MODE warning on initialization

    Example:
        stub = EntropySourceStub()

        # Use default entropy
        entropy = await stub.get_entropy()

        # Configure specific entropy for testing
        stub.set_entropy(b"test_entropy_32_bytes_exactly!")

        # Simulate failure
        stub.set_failure(True)
        await stub.get_entropy()  # Raises EntropyUnavailableError
    """

    # Source identifier for this stub
    SOURCE_IDENTIFIER = "dev-stub"

    def __init__(
        self,
        initial_entropy: bytes | None = None,
        warn_on_init: bool = True,
    ) -> None:
        """Initialize entropy source stub.

        Args:
            initial_entropy: Initial entropy bytes (defaults to SHA-256 of "test_seed")
            warn_on_init: If True, emit DEV MODE warning (default True)
        """
        if warn_on_init:
            warnings.warn(DEV_MODE_WARNING, UserWarning, stacklevel=2)

        self._entropy = initial_entropy or self._default_entropy()
        self._should_fail = False
        self._failure_reason: str | None = None
        self._is_available = True

    @staticmethod
    def _default_entropy() -> bytes:
        """Generate default entropy from predictable seed."""
        return hashlib.sha256(b"test_seed_for_stub").digest()

    async def get_entropy(self) -> bytes:
        """Get entropy bytes.

        Returns:
            The configured entropy bytes (at least 32 bytes).

        Raises:
            EntropyUnavailableError: If failure simulation is enabled.
        """
        if self._should_fail:
            raise EntropyUnavailableError(
                source_identifier=self.SOURCE_IDENTIFIER,
                reason=self._failure_reason or "Simulated entropy failure",
            )

        return self._entropy

    async def get_source_identifier(self) -> str:
        """Get identifier for this stub source."""
        return self.SOURCE_IDENTIFIER

    async def is_available(self) -> bool:
        """Check if stub is configured as available."""
        return self._is_available and not self._should_fail

    # Test control methods

    def set_entropy(self, entropy: bytes) -> None:
        """Set the entropy value for testing.

        Args:
            entropy: The entropy bytes to return from get_entropy().
                Should be at least 32 bytes for proper testing.
        """
        if len(entropy) < 32:
            warnings.warn(
                f"Entropy shorter than 32 bytes ({len(entropy)}). "
                "Production requires at least 32 bytes.",
                UserWarning,
                stacklevel=2,
            )
        self._entropy = entropy

    def set_entropy_from_seed(self, seed: str) -> None:
        """Set entropy derived from a string seed.

        Convenience method for deterministic test setup.

        Args:
            seed: String seed to hash into entropy.
        """
        self._entropy = hashlib.sha256(seed.encode("utf-8")).digest()

    def set_failure(self, should_fail: bool, reason: str | None = None) -> None:
        """Configure failure simulation.

        Args:
            should_fail: If True, get_entropy() will raise EntropyUnavailableError
            reason: Optional reason to include in the error
        """
        self._should_fail = should_fail
        self._failure_reason = reason

    def set_availability(self, is_available: bool) -> None:
        """Configure availability status.

        Args:
            is_available: The value to return from is_available()
        """
        self._is_available = is_available

    def reset(self) -> None:
        """Reset stub to default state."""
        self._entropy = self._default_entropy()
        self._should_fail = False
        self._failure_reason = None
        self._is_available = True

    @property
    def current_entropy(self) -> bytes:
        """Get the currently configured entropy (for test assertions)."""
        return self._entropy


class SecureEntropySourceStub(EntropySourceProtocol):
    """Stub that uses OS random for more realistic testing.

    This stub uses os.urandom() for entropy, providing unpredictable
    values while still being a stub (not a real external source).

    Use this when you want realistic randomness behavior in tests
    but don't need deterministic reproduction.

    WARNING: Still NOT for production - no external entropy.
    """

    SOURCE_IDENTIFIER = "dev-secure-stub"

    def __init__(self, warn_on_init: bool = True) -> None:
        """Initialize secure entropy stub.

        Args:
            warn_on_init: If True, emit DEV MODE warning
        """
        if warn_on_init:
            warnings.warn(
                "[DEV MODE] SecureEntropySourceStub - uses os.urandom, NOT external",
                UserWarning,
                stacklevel=2,
            )

        self._should_fail = False
        self._failure_reason: str | None = None

    async def get_entropy(self) -> bytes:
        """Get 32 bytes from os.urandom()."""
        if self._should_fail:
            raise EntropyUnavailableError(
                source_identifier=self.SOURCE_IDENTIFIER,
                reason=self._failure_reason or "Simulated failure",
            )
        return os.urandom(32)

    async def get_source_identifier(self) -> str:
        """Get identifier for this stub source."""
        return self.SOURCE_IDENTIFIER

    async def is_available(self) -> bool:
        """Always available unless failure is simulated."""
        return not self._should_fail

    def set_failure(self, should_fail: bool, reason: str | None = None) -> None:
        """Configure failure simulation."""
        self._should_fail = should_fail
        self._failure_reason = reason
