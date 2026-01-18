"""Unit tests for hash verification domain errors (Story 6.8, FR125).

Tests HashVerificationError and related exceptions.
"""

from __future__ import annotations

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.hash_verification import (
    HashChainBrokenError,
    HashMismatchError,
    HashVerificationError,
    HashVerificationScanInProgressError,
    HashVerificationTimeoutError,
)


class TestHashVerificationError:
    """Tests for HashVerificationError base class."""

    def test_inheritance(self) -> None:
        """Test that HashVerificationError inherits from ConstitutionalViolationError."""
        error = HashVerificationError("Test error")
        assert isinstance(error, ConstitutionalViolationError)

    def test_message(self) -> None:
        """Test error message."""
        error = HashVerificationError("Test error message")
        assert str(error) == "Test error message"


class TestHashMismatchError:
    """Tests for HashMismatchError."""

    def test_attributes(self) -> None:
        """Test error attributes."""
        error = HashMismatchError(
            event_id="event-123",
            expected_hash="abc123...",
            actual_hash="xyz789...",
        )

        assert error.event_id == "event-123"
        assert error.expected_hash == "abc123..."
        assert error.actual_hash == "xyz789..."

    def test_message_format(self) -> None:
        """Test error message format includes FR125."""
        error = HashMismatchError(
            event_id="event-123",
            expected_hash="abc123...",
            actual_hash="xyz789...",
        )

        assert "FR125" in str(error)
        assert "event-123" in str(error)
        assert "chain integrity compromised" in str(error)

    def test_inheritance(self) -> None:
        """Test inheritance from HashVerificationError."""
        error = HashMismatchError(
            event_id="event-123",
            expected_hash="abc123...",
            actual_hash="xyz789...",
        )
        assert isinstance(error, HashVerificationError)


class TestHashVerificationTimeoutError:
    """Tests for HashVerificationTimeoutError."""

    def test_attributes(self) -> None:
        """Test error attributes."""
        error = HashVerificationTimeoutError(
            scan_id="scan-123",
            timeout_seconds=600.0,
        )

        assert error.scan_id == "scan-123"
        assert error.timeout_seconds == 600.0

    def test_message_format(self) -> None:
        """Test error message format."""
        error = HashVerificationTimeoutError(
            scan_id="scan-123",
            timeout_seconds=600.0,
        )

        assert "scan-123" in str(error)
        assert "600" in str(error)
        assert "timed out" in str(error)


class TestHashVerificationScanInProgressError:
    """Tests for HashVerificationScanInProgressError."""

    def test_attributes(self) -> None:
        """Test error attributes."""
        error = HashVerificationScanInProgressError(active_scan_id="scan-123")
        assert error.active_scan_id == "scan-123"

    def test_message_format(self) -> None:
        """Test error message format."""
        error = HashVerificationScanInProgressError(active_scan_id="scan-123")
        assert "scan-123" in str(error)
        assert "already in progress" in str(error)


class TestHashChainBrokenError:
    """Tests for HashChainBrokenError."""

    def test_attributes(self) -> None:
        """Test error attributes."""
        error = HashChainBrokenError(
            event_sequence=42,
            expected_prev_hash="abc123...",
            actual_prev_hash="xyz789...",
        )

        assert error.event_sequence == 42
        assert error.expected_prev_hash == "abc123..."
        assert error.actual_prev_hash == "xyz789..."

    def test_message_format(self) -> None:
        """Test error message format includes FR125."""
        error = HashChainBrokenError(
            event_sequence=42,
            expected_prev_hash="abc123...",
            actual_prev_hash="xyz789...",
        )

        assert "FR125" in str(error)
        assert "42" in str(error)
        assert "chain integrity compromised" in str(error)

    def test_inheritance(self) -> None:
        """Test inheritance from HashVerificationError."""
        error = HashChainBrokenError(
            event_sequence=42,
            expected_prev_hash="abc123...",
            actual_prev_hash="xyz789...",
        )
        assert isinstance(error, HashVerificationError)
