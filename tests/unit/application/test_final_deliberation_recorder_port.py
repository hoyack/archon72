"""Unit tests for FinalDeliberationRecorder protocol (Story 7.8, FR135).

Tests the protocol definition for final deliberation recording.

Constitutional Constraints:
- FR135: Before cessation, final deliberation SHALL be recorded
- CT-12: Witnessing creates accountability

Test Coverage:
- Protocol method signatures
- Protocol abstract method requirements
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import pytest

from src.application.ports.final_deliberation_recorder import (
    FinalDeliberationRecorder,
    RecordDeliberationResult,
)


class TestRecordDeliberationResult:
    """Tests for RecordDeliberationResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create a successful result."""
        event_id = uuid4()
        recorded_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)

        result = RecordDeliberationResult(
            success=True,
            event_id=event_id,
            recorded_at=recorded_at,
            error_code=None,
            error_message=None,
        )

        assert result.success is True
        assert result.event_id == event_id
        assert result.recorded_at == recorded_at
        assert result.error_code is None
        assert result.error_message is None

    def test_create_failure_result(self) -> None:
        """Should create a failure result with error details."""
        result = RecordDeliberationResult(
            success=False,
            event_id=None,
            recorded_at=None,
            error_code="EVENT_STORE_WRITE_FAILED",
            error_message="Database connection timeout",
        )

        assert result.success is False
        assert result.event_id is None
        assert result.recorded_at is None
        assert result.error_code == "EVENT_STORE_WRITE_FAILED"
        assert result.error_message == "Database connection timeout"

    def test_result_is_frozen(self) -> None:
        """RecordDeliberationResult should be immutable."""
        result = RecordDeliberationResult(
            success=True,
            event_id=uuid4(),
            recorded_at=datetime.now(timezone.utc),
            error_code=None,
            error_message=None,
        )

        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


class TestFinalDeliberationRecorderProtocol:
    """Tests for FinalDeliberationRecorder protocol."""

    def test_protocol_requires_record_deliberation(self) -> None:
        """Protocol should require record_deliberation method."""
        # Verify the method exists in the protocol
        assert hasattr(FinalDeliberationRecorder, "record_deliberation")

    def test_protocol_requires_record_failure(self) -> None:
        """Protocol should require record_failure method."""
        assert hasattr(FinalDeliberationRecorder, "record_failure")

    def test_protocol_can_be_implemented(self) -> None:
        """A concrete class should be able to implement the protocol."""
        from src.domain.events.cessation_deliberation import (
            CessationDeliberationEventPayload,
        )
        from src.domain.events.deliberation_recording_failed import (
            DeliberationRecordingFailedEventPayload,
        )

        class FakeRecorder(FinalDeliberationRecorder):
            async def record_deliberation(
                self,
                payload: CessationDeliberationEventPayload,
            ) -> RecordDeliberationResult:
                return RecordDeliberationResult(
                    success=True,
                    event_id=uuid4(),
                    recorded_at=datetime.now(timezone.utc),
                    error_code=None,
                    error_message=None,
                )

            async def record_failure(
                self,
                payload: DeliberationRecordingFailedEventPayload,
            ) -> RecordDeliberationResult:
                return RecordDeliberationResult(
                    success=True,
                    event_id=uuid4(),
                    recorded_at=datetime.now(timezone.utc),
                    error_code=None,
                    error_message=None,
                )

        # Should not raise
        recorder = FakeRecorder()
        assert recorder is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be runtime checkable."""
        from src.domain.events.cessation_deliberation import (
            CessationDeliberationEventPayload,
        )
        from src.domain.events.deliberation_recording_failed import (
            DeliberationRecordingFailedEventPayload,
        )

        class ValidRecorder(FinalDeliberationRecorder):
            async def record_deliberation(
                self,
                payload: CessationDeliberationEventPayload,
            ) -> RecordDeliberationResult:
                return RecordDeliberationResult(
                    success=True,
                    event_id=uuid4(),
                    recorded_at=datetime.now(timezone.utc),
                    error_code=None,
                    error_message=None,
                )

            async def record_failure(
                self,
                payload: DeliberationRecordingFailedEventPayload,
            ) -> RecordDeliberationResult:
                return RecordDeliberationResult(
                    success=True,
                    event_id=uuid4(),
                    recorded_at=datetime.now(timezone.utc),
                    error_code=None,
                    error_message=None,
                )

        recorder = ValidRecorder()
        assert isinstance(recorder, FinalDeliberationRecorder)
