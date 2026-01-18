"""Unit tests for configuration floor violation events (Story 6.10, NFR39).

Tests for ConfigurationFloorViolationEventPayload and ConfigurationSource enum.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Violation events MUST be witnessed
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.configuration_floor import (
    CONFIGURATION_FLOOR_VIOLATION_EVENT_TYPE,
    ConfigurationFloorViolationEventPayload,
    ConfigurationSource,
)


class TestConfigurationSource:
    """Tests for ConfigurationSource enum."""

    def test_startup_source_exists(self) -> None:
        """ConfigurationSource should have STARTUP value."""
        assert ConfigurationSource.STARTUP.value == "STARTUP"

    def test_runtime_api_source_exists(self) -> None:
        """ConfigurationSource should have RUNTIME_API value."""
        assert ConfigurationSource.RUNTIME_API.value == "RUNTIME_API"

    def test_runtime_env_source_exists(self) -> None:
        """ConfigurationSource should have RUNTIME_ENV value."""
        assert ConfigurationSource.RUNTIME_ENV.value == "RUNTIME_ENV"

    def test_runtime_file_source_exists(self) -> None:
        """ConfigurationSource should have RUNTIME_FILE value."""
        assert ConfigurationSource.RUNTIME_FILE.value == "RUNTIME_FILE"


class TestConfigurationFloorViolationEventPayload:
    """Tests for ConfigurationFloorViolationEventPayload."""

    def test_event_type_constant(self) -> None:
        """Event type constant should be configuration.floor_violation."""
        assert (
            CONFIGURATION_FLOOR_VIOLATION_EVENT_TYPE == "configuration.floor_violation"
        )

    def test_create_with_all_fields(self) -> None:
        """Should create payload with all required fields."""
        violation_id = str(uuid4())
        detected_at = datetime.now(timezone.utc)

        payload = ConfigurationFloorViolationEventPayload(
            violation_id=violation_id,
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
            source=ConfigurationSource.STARTUP,
            detected_at=detected_at,
        )

        assert payload.violation_id == violation_id
        assert payload.threshold_name == "cessation_breach_count"
        assert payload.attempted_value == 5
        assert payload.constitutional_floor == 10
        assert payload.fr_reference == "FR32"
        assert payload.source == ConfigurationSource.STARTUP
        assert payload.detected_at == detected_at

    def test_create_with_float_values(self) -> None:
        """Should support float values for thresholds like topic_diversity."""
        payload = ConfigurationFloorViolationEventPayload(
            violation_id=str(uuid4()),
            threshold_name="topic_diversity_threshold",
            attempted_value=0.15,
            constitutional_floor=0.30,
            fr_reference="FR73",
            source=ConfigurationSource.RUNTIME_API,
            detected_at=datetime.now(timezone.utc),
        )

        assert payload.attempted_value == 0.15
        assert payload.constitutional_floor == 0.30

    def test_frozen_dataclass(self) -> None:
        """Payload should be immutable (frozen dataclass)."""
        payload = ConfigurationFloorViolationEventPayload(
            violation_id=str(uuid4()),
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
            source=ConfigurationSource.STARTUP,
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.threshold_name = "modified"  # type: ignore[misc]

    def test_to_dict_structure(self) -> None:
        """to_dict() should return expected dictionary structure."""
        violation_id = str(uuid4())
        detected_at = datetime.now(timezone.utc)

        payload = ConfigurationFloorViolationEventPayload(
            violation_id=violation_id,
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
            source=ConfigurationSource.STARTUP,
            detected_at=detected_at,
        )

        result = payload.to_dict()

        assert result["violation_id"] == violation_id
        assert result["threshold_name"] == "cessation_breach_count"
        assert result["attempted_value"] == 5
        assert result["constitutional_floor"] == 10
        assert result["fr_reference"] == "FR32"
        assert result["source"] == "STARTUP"
        assert result["detected_at"] == detected_at.isoformat()

    def test_signable_content_deterministic(self) -> None:
        """signable_content() should be deterministic for CT-12 witnessing."""
        violation_id = str(uuid4())
        detected_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        payload = ConfigurationFloorViolationEventPayload(
            violation_id=violation_id,
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
            source=ConfigurationSource.STARTUP,
            detected_at=detected_at,
        )

        # Call signable_content multiple times
        content1 = payload.signable_content()
        content2 = payload.signable_content()

        # Should be identical (deterministic)
        assert content1 == content2

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content() should return bytes for signing."""
        payload = ConfigurationFloorViolationEventPayload(
            violation_id=str(uuid4()),
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
            source=ConfigurationSource.STARTUP,
            detected_at=datetime.now(timezone.utc),
        )

        content = payload.signable_content()

        assert isinstance(content, bytes)

    def test_signable_content_different_for_different_payloads(self) -> None:
        """Different payloads should produce different signable content."""
        detected_at = datetime.now(timezone.utc)

        payload1 = ConfigurationFloorViolationEventPayload(
            violation_id=str(uuid4()),
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
            source=ConfigurationSource.STARTUP,
            detected_at=detected_at,
        )

        payload2 = ConfigurationFloorViolationEventPayload(
            violation_id=str(uuid4()),
            threshold_name="recovery_waiting_hours",
            attempted_value=24,
            constitutional_floor=48,
            fr_reference="NFR41",
            source=ConfigurationSource.RUNTIME_API,
            detected_at=detected_at,
        )

        assert payload1.signable_content() != payload2.signable_content()

    def test_signable_content_includes_all_fields(self) -> None:
        """signable_content() should include all fields for verification."""
        violation_id = str(uuid4())
        detected_at = datetime.now(timezone.utc)

        payload = ConfigurationFloorViolationEventPayload(
            violation_id=violation_id,
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
            source=ConfigurationSource.STARTUP,
            detected_at=detected_at,
        )

        content = payload.signable_content()
        content_str = content.decode("utf-8")

        # Verify all critical fields are in the content
        assert violation_id in content_str
        assert "cessation_breach_count" in content_str
        assert "5" in content_str  # attempted_value
        assert "10" in content_str  # constitutional_floor
        assert "FR32" in content_str
        assert "STARTUP" in content_str

    def test_all_sources_supported(self) -> None:
        """Should support all ConfigurationSource values."""
        detected_at = datetime.now(timezone.utc)

        for source in ConfigurationSource:
            payload = ConfigurationFloorViolationEventPayload(
                violation_id=str(uuid4()),
                threshold_name="cessation_breach_count",
                attempted_value=5,
                constitutional_floor=10,
                fr_reference="FR32",
                source=source,
                detected_at=detected_at,
            )

            assert payload.source == source
            assert payload.to_dict()["source"] == source.value
