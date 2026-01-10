"""Unit tests for hash verification domain events (Story 6.8, FR125).

Tests HashVerificationBreachEventPayload and HashVerificationCompletedEventPayload.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.domain.events.hash_verification import (
    HASH_VERIFICATION_BREACH_EVENT_TYPE,
    HASH_VERIFICATION_COMPLETED_EVENT_TYPE,
    HashVerificationBreachEventPayload,
    HashVerificationCompletedEventPayload,
    HashVerificationResult,
)


class TestHashVerificationBreachEventPayload:
    """Tests for HashVerificationBreachEventPayload."""

    def test_create_valid_payload(self) -> None:
        """Test creating a valid breach payload."""
        now = datetime.now(timezone.utc)
        payload = HashVerificationBreachEventPayload(
            breach_id="breach-123",
            affected_event_id="event-456",
            expected_hash="abc123...",
            actual_hash="xyz789...",
            event_sequence_num=42,
            detected_at=now,
        )

        assert payload.breach_id == "breach-123"
        assert payload.affected_event_id == "event-456"
        assert payload.expected_hash == "abc123..."
        assert payload.actual_hash == "xyz789..."
        assert payload.event_sequence_num == 42
        assert payload.detected_at == now

    def test_empty_breach_id_validation(self) -> None:
        """Test that breach_id cannot be empty."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="breach_id cannot be empty"):
            HashVerificationBreachEventPayload(
                breach_id="",
                affected_event_id="event-456",
                expected_hash="abc123...",
                actual_hash="xyz789...",
                event_sequence_num=42,
                detected_at=now,
            )

    def test_matching_hashes_validation(self) -> None:
        """Test that expected and actual hashes cannot be equal."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="cannot be equal in a breach event"):
            HashVerificationBreachEventPayload(
                breach_id="breach-123",
                affected_event_id="event-456",
                expected_hash="same_hash",
                actual_hash="same_hash",
                event_sequence_num=42,
                detected_at=now,
            )

    def test_negative_sequence_validation(self) -> None:
        """Test that event_sequence_num must be non-negative."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="event_sequence_num must be non-negative"):
            HashVerificationBreachEventPayload(
                breach_id="breach-123",
                affected_event_id="event-456",
                expected_hash="abc123...",
                actual_hash="xyz789...",
                event_sequence_num=-1,
                detected_at=now,
            )

    def test_signable_content(self) -> None:
        """Test signable_content produces deterministic JSON (CT-12)."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = HashVerificationBreachEventPayload(
            breach_id="breach-123",
            affected_event_id="event-456",
            expected_hash="abc123...",
            actual_hash="xyz789...",
            event_sequence_num=42,
            detected_at=now,
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

        data = json.loads(content.decode("utf-8"))
        assert data["event_type"] == HASH_VERIFICATION_BREACH_EVENT_TYPE
        assert data["breach_id"] == "breach-123"
        assert data["event_sequence_num"] == 42

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        now = datetime.now(timezone.utc)
        payload = HashVerificationBreachEventPayload(
            breach_id="breach-123",
            affected_event_id="event-456",
            expected_hash="abc123...",
            actual_hash="xyz789...",
            event_sequence_num=42,
            detected_at=now,
        )

        data = payload.to_dict()
        assert data["breach_id"] == "breach-123"
        assert data["affected_event_id"] == "event-456"
        assert data["expected_hash"] == "abc123..."
        assert data["actual_hash"] == "xyz789..."
        assert data["event_sequence_num"] == 42


class TestHashVerificationCompletedEventPayload:
    """Tests for HashVerificationCompletedEventPayload."""

    def test_create_passed_scan(self) -> None:
        """Test creating a passed scan payload."""
        now = datetime.now(timezone.utc)
        payload = HashVerificationCompletedEventPayload(
            scan_id="scan-123",
            events_scanned=100,
            sequence_range=(0, 99),
            duration_seconds=5.5,
            result=HashVerificationResult.PASSED,
            completed_at=now,
        )

        assert payload.scan_id == "scan-123"
        assert payload.events_scanned == 100
        assert payload.sequence_range == (0, 99)
        assert payload.duration_seconds == 5.5
        assert payload.result == HashVerificationResult.PASSED
        assert payload.is_success is True

    def test_create_failed_scan(self) -> None:
        """Test creating a failed scan payload."""
        now = datetime.now(timezone.utc)
        payload = HashVerificationCompletedEventPayload(
            scan_id="scan-123",
            events_scanned=50,
            sequence_range=(0, 99),
            duration_seconds=2.5,
            result=HashVerificationResult.FAILED,
            completed_at=now,
        )

        assert payload.result == HashVerificationResult.FAILED
        assert payload.is_success is False

    def test_empty_scan_id_validation(self) -> None:
        """Test that scan_id cannot be empty."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="scan_id cannot be empty"):
            HashVerificationCompletedEventPayload(
                scan_id="",
                events_scanned=100,
                sequence_range=(0, 99),
                duration_seconds=5.5,
                result=HashVerificationResult.PASSED,
                completed_at=now,
            )

    def test_negative_events_scanned_validation(self) -> None:
        """Test that events_scanned must be non-negative."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="events_scanned must be non-negative"):
            HashVerificationCompletedEventPayload(
                scan_id="scan-123",
                events_scanned=-1,
                sequence_range=(0, 99),
                duration_seconds=5.5,
                result=HashVerificationResult.PASSED,
                completed_at=now,
            )

    def test_negative_duration_validation(self) -> None:
        """Test that duration_seconds must be non-negative."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="duration_seconds must be non-negative"):
            HashVerificationCompletedEventPayload(
                scan_id="scan-123",
                events_scanned=100,
                sequence_range=(0, 99),
                duration_seconds=-1.0,
                result=HashVerificationResult.PASSED,
                completed_at=now,
            )

    def test_invalid_sequence_range_validation(self) -> None:
        """Test that sequence_range must have exactly 2 elements."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="sequence_range must have exactly 2 elements"):
            HashVerificationCompletedEventPayload(
                scan_id="scan-123",
                events_scanned=100,
                sequence_range=(0, 50, 99),  # type: ignore
                duration_seconds=5.5,
                result=HashVerificationResult.PASSED,
                completed_at=now,
            )

    def test_signable_content(self) -> None:
        """Test signable_content produces deterministic JSON (CT-12)."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = HashVerificationCompletedEventPayload(
            scan_id="scan-123",
            events_scanned=100,
            sequence_range=(0, 99),
            duration_seconds=5.5,
            result=HashVerificationResult.PASSED,
            completed_at=now,
        )

        content = payload.signable_content()
        data = json.loads(content.decode("utf-8"))
        assert data["event_type"] == HASH_VERIFICATION_COMPLETED_EVENT_TYPE
        assert data["scan_id"] == "scan-123"
        assert data["result"] == "passed"


class TestHashVerificationResult:
    """Tests for HashVerificationResult enum."""

    def test_enum_values(self) -> None:
        """Test enum has expected values."""
        assert HashVerificationResult.PASSED.value == "passed"
        assert HashVerificationResult.FAILED.value == "failed"
