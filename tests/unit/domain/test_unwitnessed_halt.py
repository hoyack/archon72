"""Unit tests for UnwitnessedHaltRecord (Story 3.9, Task 1).

Tests the domain model for tracking halts that couldn't be written
to the event store.

Constitutional Constraints:
- CT-13: Integrity outranks availability -> halt proceeds even if write fails
- RT-2: Unwitnessed halts must be tracked for later reconciliation
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.constitutional_crisis import (
    ConstitutionalCrisisPayload,
    CrisisType,
)
from src.domain.models.unwitnessed_halt import UnwitnessedHaltRecord


class TestUnwitnessedHaltRecordCreation:
    """Tests for UnwitnessedHaltRecord creation."""

    def test_unwitnessed_halt_record_creation(self) -> None:
        """Should create UnwitnessedHaltRecord with all required fields."""
        halt_id = uuid4()
        crisis_payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Test fork detection",
            triggering_event_ids=(uuid4(), uuid4()),
            detecting_service_id="test-service",
        )
        failure_reason = "Database connection failed"
        fallback_timestamp = datetime.now(timezone.utc)

        record = UnwitnessedHaltRecord(
            halt_id=halt_id,
            crisis_payload=crisis_payload,
            failure_reason=failure_reason,
            fallback_timestamp=fallback_timestamp,
        )

        assert record.halt_id == halt_id
        assert record.crisis_payload == crisis_payload
        assert record.failure_reason == failure_reason
        assert record.fallback_timestamp == fallback_timestamp

    def test_unwitnessed_halt_record_immutable(self) -> None:
        """Should be immutable (frozen dataclass)."""
        record = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_timestamp=datetime.now(timezone.utc),
                detection_details="Test",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test",
            ),
            failure_reason="Test failure",
            fallback_timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            record.halt_id = uuid4()  # type: ignore[misc]

        with pytest.raises(AttributeError):
            record.failure_reason = "New reason"  # type: ignore[misc]


class TestUnwitnessedHaltRecordContents:
    """Tests for UnwitnessedHaltRecord content requirements."""

    def test_unwitnessed_halt_record_contains_crisis_payload(self) -> None:
        """Should contain full crisis payload for later reconciliation."""
        triggering_ids = (uuid4(), uuid4())
        crisis_payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.SEQUENCE_GAP_DETECTED,
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detection_details="Gap in sequence 100-105",
            triggering_event_ids=triggering_ids,
            detecting_service_id="gap-detector",
        )

        record = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=crisis_payload,
            failure_reason="Event store unavailable",
            fallback_timestamp=datetime.now(timezone.utc),
        )

        # Verify crisis payload is fully preserved
        assert record.crisis_payload.crisis_type == CrisisType.SEQUENCE_GAP_DETECTED
        assert record.crisis_payload.detection_details == "Gap in sequence 100-105"
        assert record.crisis_payload.triggering_event_ids == triggering_ids
        assert record.crisis_payload.detecting_service_id == "gap-detector"

    def test_unwitnessed_halt_record_contains_failure_reason(self) -> None:
        """Should contain reason why witnessing failed."""
        record = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_timestamp=datetime.now(timezone.utc),
                detection_details="Test",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test",
            ),
            failure_reason="Connection timeout after 5000ms",
            fallback_timestamp=datetime.now(timezone.utc),
        )

        assert "timeout" in record.failure_reason.lower()
        assert record.failure_reason == "Connection timeout after 5000ms"

    def test_unwitnessed_halt_record_contains_fallback_timestamp(self) -> None:
        """Should contain fallback timestamp for recovery ordering."""
        fallback_ts = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        record = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_timestamp=datetime.now(timezone.utc),
                detection_details="Test",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test",
            ),
            failure_reason="Test failure",
            fallback_timestamp=fallback_ts,
        )

        assert record.fallback_timestamp == fallback_ts


class TestUnwitnessedHaltRecordSignableContent:
    """Tests for signable content generation."""

    def test_unwitnessed_halt_record_signable_content(self) -> None:
        """Should generate signable bytes for later witnessing."""
        record = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                detection_details="Fork detected",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test-service",
            ),
            failure_reason="Test failure",
            fallback_timestamp=datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
        )

        content = record.signable_content()

        assert isinstance(content, bytes)
        assert len(content) > 0
        # Should include key fields
        content_str = content.decode("utf-8")
        assert "unwitnessed_halt" in content_str
        assert str(record.halt_id) in content_str
        assert record.failure_reason in content_str

    def test_signable_content_is_deterministic(self) -> None:
        """Same record should produce same signable content."""
        halt_id = uuid4()
        triggering_id = uuid4()
        crisis_payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detection_details="Test",
            triggering_event_ids=(triggering_id,),
            detecting_service_id="test",
        )
        fallback_ts = datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc)

        record1 = UnwitnessedHaltRecord(
            halt_id=halt_id,
            crisis_payload=crisis_payload,
            failure_reason="Test failure",
            fallback_timestamp=fallback_ts,
        )
        record2 = UnwitnessedHaltRecord(
            halt_id=halt_id,
            crisis_payload=crisis_payload,
            failure_reason="Test failure",
            fallback_timestamp=fallback_ts,
        )

        assert record1.signable_content() == record2.signable_content()


class TestUnwitnessedHaltRecordEquality:
    """Tests for equality comparison."""

    def test_unwitnessed_halt_record_equality(self) -> None:
        """Should be equal if all fields match."""
        halt_id = uuid4()
        triggering_id = uuid4()
        crisis_payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detection_details="Test",
            triggering_event_ids=(triggering_id,),
            detecting_service_id="test",
        )
        fallback_ts = datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc)

        record1 = UnwitnessedHaltRecord(
            halt_id=halt_id,
            crisis_payload=crisis_payload,
            failure_reason="Test failure",
            fallback_timestamp=fallback_ts,
        )
        record2 = UnwitnessedHaltRecord(
            halt_id=halt_id,
            crisis_payload=crisis_payload,
            failure_reason="Test failure",
            fallback_timestamp=fallback_ts,
        )

        assert record1 == record2

    def test_unwitnessed_halt_record_inequality_different_halt_id(self) -> None:
        """Should not be equal if halt_id differs."""
        crisis_payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Test",
            triggering_event_ids=(uuid4(),),
            detecting_service_id="test",
        )
        fallback_ts = datetime.now(timezone.utc)

        record1 = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=crisis_payload,
            failure_reason="Test",
            fallback_timestamp=fallback_ts,
        )
        record2 = UnwitnessedHaltRecord(
            halt_id=uuid4(),  # Different ID
            crisis_payload=crisis_payload,
            failure_reason="Test",
            fallback_timestamp=fallback_ts,
        )

        assert record1 != record2

    def test_unwitnessed_halt_record_hashable(self) -> None:
        """Should be hashable for use in sets/dicts."""
        record = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_timestamp=datetime.now(timezone.utc),
                detection_details="Test",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test",
            ),
            failure_reason="Test",
            fallback_timestamp=datetime.now(timezone.utc),
        )

        # Should be usable as dict key
        records_dict = {record: "value"}
        assert records_dict[record] == "value"

        # Should be usable in set
        records_set = {record}
        assert record in records_set
