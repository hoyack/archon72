"""Unit tests for EventReplicatorPort interface (Story 1.10).

Tests for:
- ReplicationReceipt dataclass creation and properties
- VerificationResult dataclass creation and is_valid property
- ReplicationStatus enum values
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.event_replicator import (
    ReplicationReceipt,
    ReplicationStatus,
    VerificationResult,
)


class TestReplicationStatus:
    """Tests for ReplicationStatus enum."""

    def test_status_values_exist(self) -> None:
        """All expected status values should exist."""
        assert ReplicationStatus.PENDING.value == "pending"
        assert ReplicationStatus.CONFIRMED.value == "confirmed"
        assert ReplicationStatus.FAILED.value == "failed"
        assert ReplicationStatus.NOT_CONFIGURED.value == "not_configured"


class TestReplicationReceipt:
    """Tests for ReplicationReceipt dataclass."""

    def test_create_receipt_with_all_fields(self) -> None:
        """Should create receipt with all required fields."""
        event_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        receipt = ReplicationReceipt(
            event_id=event_id,
            replica_ids=("replica-1", "replica-2"),
            status=ReplicationStatus.CONFIRMED,
            timestamp=timestamp,
        )

        assert receipt.event_id == event_id
        assert receipt.replica_ids == ("replica-1", "replica-2")
        assert receipt.status == ReplicationStatus.CONFIRMED
        assert receipt.timestamp == timestamp

    def test_receipt_is_frozen(self) -> None:
        """Receipt should be immutable (frozen dataclass)."""
        receipt = ReplicationReceipt(
            event_id=uuid4(),
            replica_ids=(),
            status=ReplicationStatus.NOT_CONFIGURED,
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            receipt.status = ReplicationStatus.FAILED  # type: ignore[misc]

    def test_receipt_with_empty_replica_ids(self) -> None:
        """Should create receipt with empty replica tuple (dev mode)."""
        receipt = ReplicationReceipt(
            event_id=uuid4(),
            replica_ids=(),
            status=ReplicationStatus.NOT_CONFIGURED,
            timestamp=datetime.now(timezone.utc),
        )

        assert receipt.replica_ids == ()
        assert receipt.status == ReplicationStatus.NOT_CONFIGURED

    def test_receipt_with_failed_status(self) -> None:
        """Should create receipt with failed status."""
        receipt = ReplicationReceipt(
            event_id=uuid4(),
            replica_ids=("replica-1",),
            status=ReplicationStatus.FAILED,
            timestamp=datetime.now(timezone.utc),
        )

        assert receipt.status == ReplicationStatus.FAILED


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_create_positive_result(self) -> None:
        """Should create result with all positive checks."""
        result = VerificationResult(
            head_hash_match=True,
            signature_valid=True,
            schema_version_match=True,
            errors=(),
        )

        assert result.head_hash_match is True
        assert result.signature_valid is True
        assert result.schema_version_match is True
        assert result.errors == ()

    def test_is_valid_all_pass(self) -> None:
        """is_valid should return True when all checks pass."""
        result = VerificationResult(
            head_hash_match=True,
            signature_valid=True,
            schema_version_match=True,
            errors=(),
        )

        assert result.is_valid is True

    def test_is_valid_hash_mismatch(self) -> None:
        """is_valid should return False when hash doesn't match."""
        result = VerificationResult(
            head_hash_match=False,
            signature_valid=True,
            schema_version_match=True,
            errors=(),
        )

        assert result.is_valid is False

    def test_is_valid_signature_invalid(self) -> None:
        """is_valid should return False when signature is invalid."""
        result = VerificationResult(
            head_hash_match=True,
            signature_valid=False,
            schema_version_match=True,
            errors=(),
        )

        assert result.is_valid is False

    def test_is_valid_schema_mismatch(self) -> None:
        """is_valid should return False when schema doesn't match."""
        result = VerificationResult(
            head_hash_match=True,
            signature_valid=True,
            schema_version_match=False,
            errors=(),
        )

        assert result.is_valid is False

    def test_is_valid_with_errors(self) -> None:
        """is_valid should return False when errors exist."""
        result = VerificationResult(
            head_hash_match=True,
            signature_valid=True,
            schema_version_match=True,
            errors=("Some error occurred",),
        )

        assert result.is_valid is False

    def test_is_valid_all_failures(self) -> None:
        """is_valid should return False when all checks fail."""
        result = VerificationResult(
            head_hash_match=False,
            signature_valid=False,
            schema_version_match=False,
            errors=("Error 1", "Error 2"),
        )

        assert result.is_valid is False

    def test_result_is_frozen(self) -> None:
        """Result should be immutable (frozen dataclass)."""
        result = VerificationResult(
            head_hash_match=True,
            signature_valid=True,
            schema_version_match=True,
            errors=(),
        )

        with pytest.raises(AttributeError):
            result.head_hash_match = False  # type: ignore[misc]
