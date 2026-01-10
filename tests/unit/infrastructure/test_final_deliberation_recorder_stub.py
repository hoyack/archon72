"""Unit tests for FinalDeliberationRecorderStub (Story 7.8, FR135).

Tests the stub implementation of FinalDeliberationRecorder for development.

Test Coverage:
- record_deliberation() returns success
- record_failure() returns success
- Configurable failure mode
- Event IDs are generated
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.final_deliberation_recorder import FinalDeliberationRecorder
from src.domain.events.cessation_deliberation import (
    ArchonDeliberation,
    ArchonPosition,
    CessationDeliberationEventPayload,
)
from src.domain.events.collective_output import VoteCounts
from src.domain.events.deliberation_recording_failed import (
    DeliberationRecordingFailedEventPayload,
)
from src.infrastructure.stubs.final_deliberation_recorder_stub import (
    FinalDeliberationRecorderStub,
)


def create_test_deliberation_payload() -> CessationDeliberationEventPayload:
    """Create a test deliberation payload with 72 archons."""
    timestamp = datetime.now(timezone.utc)
    deliberations = tuple(
        ArchonDeliberation(
            archon_id=f"archon-{i + 1:03d}",
            position=ArchonPosition.SUPPORT_CESSATION,
            reasoning=f"Test reasoning {i + 1}",
            statement_timestamp=timestamp,
        )
        for i in range(72)
    )

    return CessationDeliberationEventPayload(
        deliberation_id=uuid4(),
        deliberation_started_at=timestamp,
        deliberation_ended_at=timestamp,
        vote_recorded_at=timestamp,
        duration_seconds=100,
        archon_deliberations=deliberations,
        vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
        dissent_percentage=0.0,
    )


def create_test_failure_payload() -> DeliberationRecordingFailedEventPayload:
    """Create a test failure payload."""
    timestamp = datetime.now(timezone.utc)
    return DeliberationRecordingFailedEventPayload(
        deliberation_id=uuid4(),
        attempted_at=timestamp,
        failed_at=timestamp,
        error_code="TEST_ERROR",
        error_message="Test error message",
        retry_count=3,
        partial_archon_count=45,
    )


class TestFinalDeliberationRecorderStub:
    """Tests for FinalDeliberationRecorderStub."""

    def test_implements_protocol(self) -> None:
        """Stub should implement FinalDeliberationRecorder protocol."""
        stub = FinalDeliberationRecorderStub()
        assert isinstance(stub, FinalDeliberationRecorder)

    @pytest.mark.asyncio
    async def test_record_deliberation_success(self) -> None:
        """record_deliberation should return success by default."""
        stub = FinalDeliberationRecorderStub()
        payload = create_test_deliberation_payload()

        result = await stub.record_deliberation(payload)

        assert result.success is True
        assert result.event_id is not None
        assert result.recorded_at is not None
        assert result.error_code is None
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_record_failure_success(self) -> None:
        """record_failure should return success by default."""
        stub = FinalDeliberationRecorderStub()
        payload = create_test_failure_payload()

        result = await stub.record_failure(payload)

        assert result.success is True
        assert result.event_id is not None
        assert result.recorded_at is not None

    @pytest.mark.asyncio
    async def test_configurable_deliberation_failure(self) -> None:
        """Stub should support configured failure for deliberation."""
        stub = FinalDeliberationRecorderStub(
            deliberation_should_fail=True,
            deliberation_error_code="SIMULATED_FAILURE",
            deliberation_error_message="Deliberation recording simulated failure",
        )
        payload = create_test_deliberation_payload()

        result = await stub.record_deliberation(payload)

        assert result.success is False
        assert result.event_id is None
        assert result.recorded_at is None
        assert result.error_code == "SIMULATED_FAILURE"
        assert result.error_message == "Deliberation recording simulated failure"

    @pytest.mark.asyncio
    async def test_configurable_failure_recording_failure(self) -> None:
        """Stub should support configured failure for failure recording."""
        stub = FinalDeliberationRecorderStub(
            failure_should_fail=True,
            failure_error_code="TOTAL_FAILURE",
            failure_error_message="Cannot record anything",
        )
        payload = create_test_failure_payload()

        result = await stub.record_failure(payload)

        assert result.success is False
        assert result.event_id is None
        assert result.error_code == "TOTAL_FAILURE"

    @pytest.mark.asyncio
    async def test_recorded_event_ids_are_unique(self) -> None:
        """Each recorded event should have unique ID."""
        stub = FinalDeliberationRecorderStub()
        payload1 = create_test_deliberation_payload()
        payload2 = create_test_deliberation_payload()

        result1 = await stub.record_deliberation(payload1)
        result2 = await stub.record_deliberation(payload2)

        assert result1.event_id != result2.event_id

    @pytest.mark.asyncio
    async def test_recorded_events_tracked(self) -> None:
        """Stub should track recorded events for testing."""
        stub = FinalDeliberationRecorderStub()
        payload = create_test_deliberation_payload()

        await stub.record_deliberation(payload)

        assert len(stub.recorded_deliberations) == 1
        assert stub.recorded_deliberations[0] == payload

    @pytest.mark.asyncio
    async def test_recorded_failures_tracked(self) -> None:
        """Stub should track recorded failures for testing."""
        stub = FinalDeliberationRecorderStub()
        payload = create_test_failure_payload()

        await stub.record_failure(payload)

        assert len(stub.recorded_failures) == 1
        assert stub.recorded_failures[0] == payload

    def test_reset_clears_recorded_events(self) -> None:
        """reset() should clear all tracked events."""
        stub = FinalDeliberationRecorderStub()
        stub.recorded_deliberations.append(create_test_deliberation_payload())
        stub.recorded_failures.append(create_test_failure_payload())

        stub.reset()

        assert len(stub.recorded_deliberations) == 0
        assert len(stub.recorded_failures) == 0
