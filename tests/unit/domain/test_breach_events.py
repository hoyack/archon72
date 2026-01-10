"""Unit tests for breach event payloads (Story 6.1, FR30).

Tests for BreachEventPayload, BreachType enum, and BreachSeverity enum.

Constitutional Constraints:
- FR30: Breach declarations SHALL create constitutional events with
        breach_type, violated_requirement, detection_timestamp
- CT-12: Witnessing creates accountability -> signable_content() for witnessing
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import MappingProxyType
from uuid import UUID, uuid4

import pytest

from src.domain.events.breach import (
    BREACH_DECLARED_EVENT_TYPE,
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)


class TestBreachType:
    """Tests for BreachType enum values (FR30)."""

    def test_threshold_violation_value(self) -> None:
        """BreachType.THRESHOLD_VIOLATION has correct value."""
        assert BreachType.THRESHOLD_VIOLATION.value == "THRESHOLD_VIOLATION"

    def test_witness_collusion_value(self) -> None:
        """BreachType.WITNESS_COLLUSION has correct value."""
        assert BreachType.WITNESS_COLLUSION.value == "WITNESS_COLLUSION"

    def test_hash_mismatch_value(self) -> None:
        """BreachType.HASH_MISMATCH has correct value."""
        assert BreachType.HASH_MISMATCH.value == "HASH_MISMATCH"

    def test_signature_invalid_value(self) -> None:
        """BreachType.SIGNATURE_INVALID has correct value."""
        assert BreachType.SIGNATURE_INVALID.value == "SIGNATURE_INVALID"

    def test_constitutional_constraint_value(self) -> None:
        """BreachType.CONSTITUTIONAL_CONSTRAINT has correct value."""
        assert BreachType.CONSTITUTIONAL_CONSTRAINT.value == "CONSTITUTIONAL_CONSTRAINT"

    def test_timing_violation_value(self) -> None:
        """BreachType.TIMING_VIOLATION has correct value."""
        assert BreachType.TIMING_VIOLATION.value == "TIMING_VIOLATION"

    def test_quorum_violation_value(self) -> None:
        """BreachType.QUORUM_VIOLATION has correct value."""
        assert BreachType.QUORUM_VIOLATION.value == "QUORUM_VIOLATION"

    def test_override_abuse_value(self) -> None:
        """BreachType.OVERRIDE_ABUSE has correct value."""
        assert BreachType.OVERRIDE_ABUSE.value == "OVERRIDE_ABUSE"

    def test_all_breach_types_defined(self) -> None:
        """All required breach types are defined."""
        expected_types = {
            "THRESHOLD_VIOLATION",
            "WITNESS_COLLUSION",
            "HASH_MISMATCH",
            "SIGNATURE_INVALID",
            "CONSTITUTIONAL_CONSTRAINT",
            "TIMING_VIOLATION",
            "QUORUM_VIOLATION",
            "OVERRIDE_ABUSE",
        }
        actual_types = {bt.value for bt in BreachType}
        assert actual_types == expected_types


class TestBreachSeverity:
    """Tests for BreachSeverity enum values."""

    def test_critical_value(self) -> None:
        """BreachSeverity.CRITICAL has correct value."""
        assert BreachSeverity.CRITICAL.value == "CRITICAL"

    def test_high_value(self) -> None:
        """BreachSeverity.HIGH has correct value."""
        assert BreachSeverity.HIGH.value == "HIGH"

    def test_medium_value(self) -> None:
        """BreachSeverity.MEDIUM has correct value."""
        assert BreachSeverity.MEDIUM.value == "MEDIUM"

    def test_low_value(self) -> None:
        """BreachSeverity.LOW has correct value."""
        assert BreachSeverity.LOW.value == "LOW"

    def test_all_severities_defined(self) -> None:
        """All required severity levels are defined."""
        expected_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        actual_severities = {s.value for s in BreachSeverity}
        assert actual_severities == expected_severities


class TestBreachEventPayload:
    """Tests for BreachEventPayload dataclass (FR30, CT-12)."""

    @pytest.fixture
    def sample_payload(self) -> BreachEventPayload:
        """Create a sample payload for testing."""
        return BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({"expected_hash": "abc123", "actual_hash": "def456"}),
            source_event_id=None,
        )

    def test_payload_creation_with_required_fields(self) -> None:
        """BreachEventPayload can be created with required fields (FR30)."""
        breach_id = uuid4()
        detection_time = datetime.now(timezone.utc)
        details = MappingProxyType({"key": "value"})

        payload = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.THRESHOLD_VIOLATION,
            violated_requirement="FR33",
            severity=BreachSeverity.HIGH,
            detection_timestamp=detection_time,
            details=details,
            source_event_id=None,
        )

        assert payload.breach_id == breach_id
        assert payload.breach_type == BreachType.THRESHOLD_VIOLATION
        assert payload.violated_requirement == "FR33"
        assert payload.severity == BreachSeverity.HIGH
        assert payload.detection_timestamp == detection_time
        assert payload.details == details
        assert payload.source_event_id is None

    def test_payload_creation_with_source_event_id(self) -> None:
        """BreachEventPayload can include optional source_event_id."""
        breach_id = uuid4()
        source_id = uuid4()
        detection_time = datetime.now(timezone.utc)

        payload = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=detection_time,
            details=MappingProxyType({"agent_id": "archon-42"}),
            source_event_id=source_id,
        )

        assert payload.source_event_id == source_id

    def test_payload_is_frozen(self, sample_payload: BreachEventPayload) -> None:
        """BreachEventPayload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_payload.breach_type = BreachType.TIMING_VIOLATION  # type: ignore[misc]

    def test_payload_equality(self) -> None:
        """Two payloads with same fields are equal."""
        breach_id = uuid4()
        detection_time = datetime.now(timezone.utc)
        details = MappingProxyType({"key": "value"})

        payload1 = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.HIGH,
            detection_timestamp=detection_time,
            details=details,
            source_event_id=None,
        )

        payload2 = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.HIGH,
            detection_timestamp=detection_time,
            details=details,
            source_event_id=None,
        )

        assert payload1 == payload2

    def test_payload_inequality_different_type(self) -> None:
        """Two payloads with different breach_type are not equal."""
        breach_id = uuid4()
        detection_time = datetime.now(timezone.utc)

        payload1 = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.HIGH,
            detection_timestamp=detection_time,
            details=MappingProxyType({}),
            source_event_id=None,
        )

        payload2 = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR82",
            severity=BreachSeverity.HIGH,
            detection_timestamp=detection_time,
            details=MappingProxyType({}),
            source_event_id=None,
        )

        assert payload1 != payload2


class TestBreachEventPayloadSignableContent:
    """Tests for signable_content() method (CT-12 witnessing)."""

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content() returns bytes (CT-12)."""
        payload = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({"key": "value"}),
            source_event_id=None,
        )

        result = payload.signable_content()

        assert isinstance(result, bytes)

    def test_signable_content_is_valid_json(self) -> None:
        """signable_content() returns valid JSON bytes."""
        payload = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.THRESHOLD_VIOLATION,
            violated_requirement="FR33",
            severity=BreachSeverity.HIGH,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({"threshold": 10, "actual": 5}),
            source_event_id=None,
        )

        result = payload.signable_content()
        parsed = json.loads(result.decode("utf-8"))

        assert isinstance(parsed, dict)
        assert "breach_type" in parsed
        assert "violated_requirement" in parsed

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content() returns same bytes for same payload (deterministic)."""
        breach_id = uuid4()
        detection_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        payload = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.WITNESS_COLLUSION,
            violated_requirement="FR59",
            severity=BreachSeverity.MEDIUM,
            detection_timestamp=detection_time,
            details=MappingProxyType({"witness_pair": ["w1", "w2"]}),
            source_event_id=None,
        )

        result1 = payload.signable_content()
        result2 = payload.signable_content()

        assert result1 == result2

    def test_signable_content_includes_all_fields(self) -> None:
        """signable_content() includes all payload fields (FR30)."""
        breach_id = uuid4()
        detection_time = datetime.now(timezone.utc)

        payload = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
            violated_requirement="FR80",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=detection_time,
            details=MappingProxyType({"action": "delete_event"}),
            source_event_id=None,
        )

        result = payload.signable_content()
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["breach_id"] == str(breach_id)
        assert parsed["breach_type"] == "CONSTITUTIONAL_CONSTRAINT"
        assert parsed["violated_requirement"] == "FR80"
        assert parsed["severity"] == "CRITICAL"
        assert parsed["detection_timestamp"] == detection_time.isoformat()
        assert parsed["details"] == {"action": "delete_event"}

    def test_signable_content_includes_source_event_id_when_present(self) -> None:
        """signable_content() includes source_event_id when provided."""
        breach_id = uuid4()
        source_id = uuid4()
        detection_time = datetime.now(timezone.utc)

        payload = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=detection_time,
            details=MappingProxyType({}),
            source_event_id=source_id,
        )

        result = payload.signable_content()
        parsed = json.loads(result.decode("utf-8"))

        assert parsed["source_event_id"] == str(source_id)

    def test_signable_content_excludes_source_event_id_when_none(self) -> None:
        """signable_content() excludes source_event_id when None."""
        payload = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.TIMING_VIOLATION,
            violated_requirement="FR21",
            severity=BreachSeverity.HIGH,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({}),
            source_event_id=None,
        )

        result = payload.signable_content()
        parsed = json.loads(result.decode("utf-8"))

        assert "source_event_id" not in parsed

    def test_signable_content_sorted_keys(self) -> None:
        """signable_content() uses sorted keys for determinism."""
        payload = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.QUORUM_VIOLATION,
            violated_requirement="FR9",
            severity=BreachSeverity.MEDIUM,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({"z_key": 1, "a_key": 2}),
            source_event_id=None,
        )

        result = payload.signable_content()
        json_str = result.decode("utf-8")

        # In sorted JSON, "a_key" should appear before "z_key" within details
        a_pos = json_str.find('"a_key"')
        z_pos = json_str.find('"z_key"')
        assert a_pos < z_pos


class TestBreachDeclaredEventType:
    """Tests for BREACH_DECLARED_EVENT_TYPE constant."""

    def test_event_type_value(self) -> None:
        """Event type constant has correct value."""
        assert BREACH_DECLARED_EVENT_TYPE == "breach.declared"

    def test_event_type_is_string(self) -> None:
        """Event type constant is a string."""
        assert isinstance(BREACH_DECLARED_EVENT_TYPE, str)
