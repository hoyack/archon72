"""Unit tests for SeparationEnforcementService (Story 8.2, FR52).

Tests the service that enforces operational-constitutional separation.
"""

import pytest

from src.application.services.separation_enforcement_service import (
    SeparationEnforcementService,
    ValidationResult,
    WriteTarget,
)
from src.domain.errors.separation import OperationalToEventStoreError
from src.infrastructure.stubs.separation_validator_stub import SeparationValidatorStub


class TestWriteTargetEnum:
    """Test WriteTarget enum."""

    def test_event_store_value(self) -> None:
        """Test EVENT_STORE value."""
        assert WriteTarget.EVENT_STORE.value == "event_store"

    def test_prometheus_value(self) -> None:
        """Test PROMETHEUS value."""
        assert WriteTarget.PROMETHEUS.value == "prometheus"

    def test_operational_db_value(self) -> None:
        """Test OPERATIONAL_DB value."""
        assert WriteTarget.OPERATIONAL_DB.value == "operational_db"


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_valid_result(self) -> None:
        """Test creating a valid result."""
        result = ValidationResult(valid=True, reason="Data correctly routed")
        assert result.valid is True
        assert result.reason == "Data correctly routed"

    def test_invalid_result(self) -> None:
        """Test creating an invalid result."""
        result = ValidationResult(valid=False, reason="FR52 violation")
        assert result.valid is False
        assert result.reason == "FR52 violation"


class TestValidateWriteTarget:
    """Test validate_write_target method."""

    @pytest.fixture
    def service(self) -> SeparationEnforcementService:
        """Create service with stub validator."""
        validator = SeparationValidatorStub()
        return SeparationEnforcementService(validator)

    def test_constitutional_to_event_store_valid(
        self, service: SeparationEnforcementService
    ) -> None:
        """Test constitutional data to event store is valid."""
        result = service.validate_write_target(
            "deliberation_output", WriteTarget.EVENT_STORE
        )
        assert result.valid is True

    def test_operational_to_prometheus_valid(
        self, service: SeparationEnforcementService
    ) -> None:
        """Test operational data to Prometheus is valid."""
        result = service.validate_write_target(
            "uptime_recorded", WriteTarget.PROMETHEUS
        )
        assert result.valid is True

    def test_operational_to_event_store_invalid(
        self, service: SeparationEnforcementService
    ) -> None:
        """Test operational data to event store is invalid."""
        result = service.validate_write_target(
            "uptime_recorded", WriteTarget.EVENT_STORE
        )
        assert result.valid is False
        assert "FR52" in result.reason or "operational" in result.reason.lower()

    def test_constitutional_to_operational_db_invalid(
        self, service: SeparationEnforcementService
    ) -> None:
        """Test constitutional data to operational DB is invalid."""
        result = service.validate_write_target(
            "halt_triggered", WriteTarget.OPERATIONAL_DB
        )
        assert result.valid is False

    def test_unknown_type_to_event_store_invalid(
        self, service: SeparationEnforcementService
    ) -> None:
        """Test unknown type to event store is invalid (fail-safe)."""
        result = service.validate_write_target(
            "random_unknown_type", WriteTarget.EVENT_STORE
        )
        assert result.valid is False


class TestAssertNotEventStore:
    """Test assert_not_event_store method."""

    @pytest.fixture
    def service(self) -> SeparationEnforcementService:
        """Create service with stub validator."""
        validator = SeparationValidatorStub()
        return SeparationEnforcementService(validator)

    def test_operational_type_raises_error(
        self, service: SeparationEnforcementService
    ) -> None:
        """Test operational type raises OperationalToEventStoreError."""
        with pytest.raises(OperationalToEventStoreError) as exc_info:
            service.assert_not_event_store("uptime_recorded")
        assert exc_info.value.data_type == "uptime_recorded"

    def test_constitutional_type_does_not_raise(
        self, service: SeparationEnforcementService
    ) -> None:
        """Test constitutional type does not raise."""
        # Should not raise
        service.assert_not_event_store("deliberation_output")

    def test_unknown_type_raises_error(
        self, service: SeparationEnforcementService
    ) -> None:
        """Test unknown type raises error (fail-safe, reject unknown)."""
        with pytest.raises(OperationalToEventStoreError):
            service.assert_not_event_store("unknown_type")


class TestGetConstitutionalEventTypes:
    """Test get_constitutional_event_types method."""

    @pytest.fixture
    def service(self) -> SeparationEnforcementService:
        """Create service with stub validator."""
        validator = SeparationValidatorStub()
        return SeparationEnforcementService(validator)

    def test_returns_set(self, service: SeparationEnforcementService) -> None:
        """Test method returns a set."""
        result = service.get_constitutional_event_types()
        assert isinstance(result, set)

    def test_returns_non_empty(self, service: SeparationEnforcementService) -> None:
        """Test method returns non-empty set."""
        result = service.get_constitutional_event_types()
        assert len(result) > 0

    def test_contains_known_types(self, service: SeparationEnforcementService) -> None:
        """Test contains known constitutional types."""
        result = service.get_constitutional_event_types()
        assert "deliberation_output" in result
        assert "halt_triggered" in result


class TestGetOperationalMetricTypes:
    """Test get_operational_metric_types method."""

    @pytest.fixture
    def service(self) -> SeparationEnforcementService:
        """Create service with stub validator."""
        validator = SeparationValidatorStub()
        return SeparationEnforcementService(validator)

    def test_returns_set(self, service: SeparationEnforcementService) -> None:
        """Test method returns a set."""
        result = service.get_operational_metric_types()
        assert isinstance(result, set)

    def test_returns_non_empty(self, service: SeparationEnforcementService) -> None:
        """Test method returns non-empty set."""
        result = service.get_operational_metric_types()
        assert len(result) > 0

    def test_contains_known_types(self, service: SeparationEnforcementService) -> None:
        """Test contains known operational types."""
        result = service.get_operational_metric_types()
        assert "uptime_recorded" in result
        assert "latency_measured" in result
