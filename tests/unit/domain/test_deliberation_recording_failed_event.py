"""Unit tests for DeliberationRecordingFailedEventPayload (Story 7.8, FR135).

Tests the deliberation recording failure event payload which captures
the failure as the final event when deliberation recording fails.

Constitutional Constraints:
- FR135: If recording fails, that failure is the final event
- CT-11: Silent failure destroys legitimacy - failure must be logged
- CT-12: Witnessing creates accountability - failure must be witnessed

Test Coverage:
- DeliberationRecordingFailedEventPayload validation
- signable_content() determinism
- to_dict() serialization
- Error code and message capture
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.deliberation_recording_failed import (
    DELIBERATION_RECORDING_FAILED_EVENT_TYPE,
    DeliberationRecordingFailedEventPayload,
)


class TestDeliberationRecordingFailedEventPayload:
    """Tests for DeliberationRecordingFailedEventPayload."""

    def test_create_valid_payload(self) -> None:
        """Should create a valid failure payload."""
        deliberation_id = uuid4()
        attempted_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        failed_at = datetime(2026, 1, 8, 12, 0, 5, tzinfo=timezone.utc)

        payload = DeliberationRecordingFailedEventPayload(
            deliberation_id=deliberation_id,
            attempted_at=attempted_at,
            failed_at=failed_at,
            error_code="EVENT_STORE_WRITE_FAILED",
            error_message="Database connection timeout after 30s",
            retry_count=3,
            partial_archon_count=45,
        )

        assert payload.deliberation_id == deliberation_id
        assert payload.attempted_at == attempted_at
        assert payload.failed_at == failed_at
        assert payload.error_code == "EVENT_STORE_WRITE_FAILED"
        assert payload.error_message == "Database connection timeout after 30s"
        assert payload.retry_count == 3
        assert payload.partial_archon_count == 45

    def test_event_type_constant(self) -> None:
        """Event type constant should be correctly defined."""
        assert DELIBERATION_RECORDING_FAILED_EVENT_TYPE == "cessation.deliberation_recording_failed"

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content() should return identical bytes for same data."""
        deliberation_id = uuid4()
        attempted_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        failed_at = datetime(2026, 1, 8, 12, 0, 5, tzinfo=timezone.utc)

        payload1 = DeliberationRecordingFailedEventPayload(
            deliberation_id=deliberation_id,
            attempted_at=attempted_at,
            failed_at=failed_at,
            error_code="TEST_ERROR",
            error_message="Test message",
            retry_count=2,
            partial_archon_count=0,
        )

        payload2 = DeliberationRecordingFailedEventPayload(
            deliberation_id=deliberation_id,
            attempted_at=attempted_at,
            failed_at=failed_at,
            error_code="TEST_ERROR",
            error_message="Test message",
            retry_count=2,
            partial_archon_count=0,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_differs_for_different_data(self) -> None:
        """signable_content() should differ for different data."""
        attempted_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        failed_at = datetime(2026, 1, 8, 12, 0, 5, tzinfo=timezone.utc)

        payload1 = DeliberationRecordingFailedEventPayload(
            deliberation_id=uuid4(),  # Different
            attempted_at=attempted_at,
            failed_at=failed_at,
            error_code="ERROR_A",
            error_message="Message A",
            retry_count=1,
            partial_archon_count=10,
        )

        payload2 = DeliberationRecordingFailedEventPayload(
            deliberation_id=uuid4(),  # Different
            attempted_at=attempted_at,
            failed_at=failed_at,
            error_code="ERROR_B",
            error_message="Message B",
            retry_count=2,
            partial_archon_count=20,
        )

        assert payload1.signable_content() != payload2.signable_content()

    def test_to_dict_serialization(self) -> None:
        """to_dict should serialize the payload correctly."""
        deliberation_id = uuid4()
        attempted_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        failed_at = datetime(2026, 1, 8, 12, 0, 5, tzinfo=timezone.utc)

        payload = DeliberationRecordingFailedEventPayload(
            deliberation_id=deliberation_id,
            attempted_at=attempted_at,
            failed_at=failed_at,
            error_code="DB_TIMEOUT",
            error_message="Connection lost",
            retry_count=5,
            partial_archon_count=30,
        )

        result = payload.to_dict()

        assert result["deliberation_id"] == str(deliberation_id)
        assert result["attempted_at"] == "2026-01-08T12:00:00+00:00"
        assert result["failed_at"] == "2026-01-08T12:00:05+00:00"
        assert result["error_code"] == "DB_TIMEOUT"
        assert result["error_message"] == "Connection lost"
        assert result["retry_count"] == 5
        assert result["partial_archon_count"] == 30

    def test_payload_is_frozen(self) -> None:
        """DeliberationRecordingFailedEventPayload should be immutable."""
        deliberation_id = uuid4()
        attempted_at = datetime.now(timezone.utc)
        failed_at = datetime.now(timezone.utc)

        payload = DeliberationRecordingFailedEventPayload(
            deliberation_id=deliberation_id,
            attempted_at=attempted_at,
            failed_at=failed_at,
            error_code="TEST",
            error_message="Test",
            retry_count=0,
            partial_archon_count=0,
        )

        with pytest.raises(AttributeError):
            payload.error_code = "MODIFIED"  # type: ignore[misc]

    def test_retry_count_must_be_non_negative(self) -> None:
        """retry_count must be non-negative."""
        deliberation_id = uuid4()
        attempted_at = datetime.now(timezone.utc)
        failed_at = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="retry_count"):
            DeliberationRecordingFailedEventPayload(
                deliberation_id=deliberation_id,
                attempted_at=attempted_at,
                failed_at=failed_at,
                error_code="TEST",
                error_message="Test",
                retry_count=-1,  # Invalid
                partial_archon_count=0,
            )

    def test_partial_archon_count_must_be_non_negative(self) -> None:
        """partial_archon_count must be non-negative."""
        deliberation_id = uuid4()
        attempted_at = datetime.now(timezone.utc)
        failed_at = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="partial_archon_count"):
            DeliberationRecordingFailedEventPayload(
                deliberation_id=deliberation_id,
                attempted_at=attempted_at,
                failed_at=failed_at,
                error_code="TEST",
                error_message="Test",
                retry_count=0,
                partial_archon_count=-5,  # Invalid
            )

    def test_partial_archon_count_cannot_exceed_72(self) -> None:
        """partial_archon_count cannot exceed 72 (the max Archon count)."""
        deliberation_id = uuid4()
        attempted_at = datetime.now(timezone.utc)
        failed_at = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="partial_archon_count.*72"):
            DeliberationRecordingFailedEventPayload(
                deliberation_id=deliberation_id,
                attempted_at=attempted_at,
                failed_at=failed_at,
                error_code="TEST",
                error_message="Test",
                retry_count=0,
                partial_archon_count=73,  # Invalid
            )

    def test_error_code_cannot_be_empty(self) -> None:
        """error_code cannot be empty."""
        deliberation_id = uuid4()
        attempted_at = datetime.now(timezone.utc)
        failed_at = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="error_code"):
            DeliberationRecordingFailedEventPayload(
                deliberation_id=deliberation_id,
                attempted_at=attempted_at,
                failed_at=failed_at,
                error_code="",  # Invalid
                error_message="Test",
                retry_count=0,
                partial_archon_count=0,
            )

    def test_error_message_can_be_empty(self) -> None:
        """error_message may be empty (code is enough context)."""
        deliberation_id = uuid4()
        attempted_at = datetime.now(timezone.utc)
        failed_at = datetime.now(timezone.utc)

        payload = DeliberationRecordingFailedEventPayload(
            deliberation_id=deliberation_id,
            attempted_at=attempted_at,
            failed_at=failed_at,
            error_code="UNKNOWN_ERROR",
            error_message="",  # Valid
            retry_count=0,
            partial_archon_count=0,
        )

        assert payload.error_message == ""

    def test_zero_retry_zero_partial_is_valid(self) -> None:
        """Zero retries and zero partial collected is valid (immediate failure)."""
        deliberation_id = uuid4()
        attempted_at = datetime.now(timezone.utc)
        failed_at = datetime.now(timezone.utc)

        payload = DeliberationRecordingFailedEventPayload(
            deliberation_id=deliberation_id,
            attempted_at=attempted_at,
            failed_at=failed_at,
            error_code="INIT_FAILED",
            error_message="Failed before collecting any deliberations",
            retry_count=0,
            partial_archon_count=0,
        )

        assert payload.retry_count == 0
        assert payload.partial_archon_count == 0
