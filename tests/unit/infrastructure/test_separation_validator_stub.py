"""Unit tests for SeparationValidatorStub (Story 8.2, FR52).

Tests the stub implementation of SeparationValidatorPort.
"""

import pytest

from src.application.ports.separation_validator import (
    DataClassification,
    SeparationValidatorPort,
)
from src.infrastructure.stubs.separation_validator_stub import SeparationValidatorStub


class TestSeparationValidatorStubProtocol:
    """Test that stub implements the protocol."""

    def test_stub_implements_protocol(self) -> None:
        """Test SeparationValidatorStub implements SeparationValidatorPort."""
        stub = SeparationValidatorStub()
        assert isinstance(stub, SeparationValidatorPort)


class TestClassifyDataConstitutional:
    """Test classification of constitutional event types."""

    @pytest.fixture
    def stub(self) -> SeparationValidatorStub:
        """Create stub instance."""
        return SeparationValidatorStub()

    def test_classify_deliberation_output(self, stub: SeparationValidatorStub) -> None:
        """Test deliberation output is classified as constitutional."""
        result = stub.classify_data("deliberation_output")
        assert result == DataClassification.CONSTITUTIONAL

    def test_classify_vote_cast(self, stub: SeparationValidatorStub) -> None:
        """Test vote cast is classified as constitutional."""
        result = stub.classify_data("vote_cast")
        assert result == DataClassification.CONSTITUTIONAL

    def test_classify_halt_triggered(self, stub: SeparationValidatorStub) -> None:
        """Test halt triggered is classified as constitutional."""
        result = stub.classify_data("halt_triggered")
        assert result == DataClassification.CONSTITUTIONAL

    def test_classify_halt_cleared(self, stub: SeparationValidatorStub) -> None:
        """Test halt cleared is classified as constitutional."""
        result = stub.classify_data("halt_cleared")
        assert result == DataClassification.CONSTITUTIONAL

    def test_classify_witness_selection(self, stub: SeparationValidatorStub) -> None:
        """Test witness selection is classified as constitutional."""
        result = stub.classify_data("witness_selection")
        assert result == DataClassification.CONSTITUTIONAL

    def test_classify_fork_detected(self, stub: SeparationValidatorStub) -> None:
        """Test fork detected is classified as constitutional."""
        result = stub.classify_data("fork_detected")
        assert result == DataClassification.CONSTITUTIONAL

    def test_classify_cessation_executed(self, stub: SeparationValidatorStub) -> None:
        """Test cessation executed is classified as constitutional."""
        result = stub.classify_data("cessation_executed")
        assert result == DataClassification.CONSTITUTIONAL

    def test_classify_breach_declared(self, stub: SeparationValidatorStub) -> None:
        """Test breach declared is classified as constitutional."""
        result = stub.classify_data("breach_declared")
        assert result == DataClassification.CONSTITUTIONAL


class TestClassifyDataOperational:
    """Test classification of operational metric types."""

    @pytest.fixture
    def stub(self) -> SeparationValidatorStub:
        """Create stub instance."""
        return SeparationValidatorStub()

    def test_classify_uptime_recorded(self, stub: SeparationValidatorStub) -> None:
        """Test uptime recorded is classified as operational."""
        result = stub.classify_data("uptime_recorded")
        assert result == DataClassification.OPERATIONAL

    def test_classify_latency_measured(self, stub: SeparationValidatorStub) -> None:
        """Test latency measured is classified as operational."""
        result = stub.classify_data("latency_measured")
        assert result == DataClassification.OPERATIONAL

    def test_classify_error_logged(self, stub: SeparationValidatorStub) -> None:
        """Test error logged is classified as operational."""
        result = stub.classify_data("error_logged")
        assert result == DataClassification.OPERATIONAL

    def test_classify_request_counted(self, stub: SeparationValidatorStub) -> None:
        """Test request counted is classified as operational."""
        result = stub.classify_data("request_counted")
        assert result == DataClassification.OPERATIONAL

    def test_classify_service_start(self, stub: SeparationValidatorStub) -> None:
        """Test service start is classified as operational."""
        result = stub.classify_data("service_start")
        assert result == DataClassification.OPERATIONAL

    def test_classify_health_check(self, stub: SeparationValidatorStub) -> None:
        """Test health check is classified as operational."""
        result = stub.classify_data("health_check")
        assert result == DataClassification.OPERATIONAL


class TestClassifyDataUnknown:
    """Test classification of unknown data types."""

    @pytest.fixture
    def stub(self) -> SeparationValidatorStub:
        """Create stub instance."""
        return SeparationValidatorStub()

    def test_classify_unknown_type(self, stub: SeparationValidatorStub) -> None:
        """Test unknown type returns UNKNOWN classification."""
        result = stub.classify_data("some_random_type")
        assert result == DataClassification.UNKNOWN

    def test_classify_empty_string(self, stub: SeparationValidatorStub) -> None:
        """Test empty string returns UNKNOWN classification."""
        result = stub.classify_data("")
        assert result == DataClassification.UNKNOWN


class TestIsConstitutional:
    """Test is_constitutional helper method."""

    @pytest.fixture
    def stub(self) -> SeparationValidatorStub:
        """Create stub instance."""
        return SeparationValidatorStub()

    def test_constitutional_type_returns_true(self, stub: SeparationValidatorStub) -> None:
        """Test constitutional type returns True."""
        assert stub.is_constitutional("deliberation_output") is True

    def test_operational_type_returns_false(self, stub: SeparationValidatorStub) -> None:
        """Test operational type returns False."""
        assert stub.is_constitutional("uptime_recorded") is False

    def test_unknown_type_returns_false(self, stub: SeparationValidatorStub) -> None:
        """Test unknown type returns False."""
        assert stub.is_constitutional("random_type") is False


class TestIsOperational:
    """Test is_operational helper method."""

    @pytest.fixture
    def stub(self) -> SeparationValidatorStub:
        """Create stub instance."""
        return SeparationValidatorStub()

    def test_operational_type_returns_true(self, stub: SeparationValidatorStub) -> None:
        """Test operational type returns True."""
        assert stub.is_operational("uptime_recorded") is True

    def test_constitutional_type_returns_false(self, stub: SeparationValidatorStub) -> None:
        """Test constitutional type returns False."""
        assert stub.is_operational("deliberation_output") is False

    def test_unknown_type_returns_false(self, stub: SeparationValidatorStub) -> None:
        """Test unknown type returns False."""
        assert stub.is_operational("random_type") is False


class TestGetAllowedEventTypes:
    """Test get_allowed_event_types method."""

    @pytest.fixture
    def stub(self) -> SeparationValidatorStub:
        """Create stub instance."""
        return SeparationValidatorStub()

    def test_returns_set(self, stub: SeparationValidatorStub) -> None:
        """Test method returns a set."""
        result = stub.get_allowed_event_types()
        assert isinstance(result, set)

    def test_returns_non_empty_set(self, stub: SeparationValidatorStub) -> None:
        """Test method returns non-empty set."""
        result = stub.get_allowed_event_types()
        assert len(result) > 0

    def test_contains_constitutional_types(self, stub: SeparationValidatorStub) -> None:
        """Test set contains known constitutional types."""
        result = stub.get_allowed_event_types()
        assert "deliberation_output" in result
        assert "vote_cast" in result
        assert "halt_triggered" in result

    def test_does_not_contain_operational_types(
        self, stub: SeparationValidatorStub
    ) -> None:
        """Test set does not contain operational types."""
        result = stub.get_allowed_event_types()
        assert "uptime_recorded" not in result
        assert "latency_measured" not in result
        assert "error_logged" not in result
