"""Unit tests for PatternViolationService (Story 8.8, AC6).

Tests for FMEA pattern violation detection from risk matrix.
"""

from enum import Enum

import pytest

from src.application.services.pattern_violation_service import (
    PatternViolationService,
)
from src.domain.errors.failure_prevention import FailureModeViolationError
from src.domain.models.pattern_violation import (
    PatternViolationType,
    ViolationSeverity,
)


@pytest.fixture
def service() -> PatternViolationService:
    """Create a PatternViolationService instance."""
    return PatternViolationService()


class TestEventType(Enum):
    """Test event type enum."""
    TEST_EVENT = "test_event"
    ANOTHER_EVENT = "another_event"


class TestValidateEventType:
    """Tests for validate_event_type method (PV-001)."""

    def test_valid_enum_event_type(self, service: PatternViolationService) -> None:
        """Test that enum event types are valid."""
        is_valid = service.validate_event_type(TestEventType.TEST_EVENT)

        assert is_valid is True

    def test_invalid_string_event_type(
        self, service: PatternViolationService
    ) -> None:
        """Test that raw string event types are invalid (PV-001)."""
        is_valid = service.validate_event_type("raw_string_event")

        assert is_valid is False

    def test_records_violation_for_string_type(
        self, service: PatternViolationService
    ) -> None:
        """Test that violation is recorded for string event type."""
        service.validate_event_type("raw_string_event")
        violations = service.detect_violations()

        assert len(violations) == 1
        assert violations[0].violation_type == PatternViolationType.RAW_STRING_EVENT_TYPE

    def test_includes_location_in_violation(
        self, service: PatternViolationService
    ) -> None:
        """Test that location is included in violation."""
        service.validate_event_type(
            "raw_string_event",
            location="test_file.py:42",
        )
        violations = service.detect_violations()

        assert violations[0].location == "test_file.py:42"


class TestValidateContentRef:
    """Tests for validate_content_ref method (PV-002)."""

    def test_valid_content_ref_prefix(
        self, service: PatternViolationService
    ) -> None:
        """Test that properly prefixed content refs are valid."""
        is_valid = service.validate_content_ref("cref-abc123def456")

        assert is_valid is True

    def test_invalid_plain_string_hash(
        self, service: PatternViolationService
    ) -> None:
        """Test that plain string hashes are invalid (PV-002)."""
        is_valid = service.validate_content_ref("abc123def456")

        assert is_valid is False

    def test_records_violation_for_plain_hash(
        self, service: PatternViolationService
    ) -> None:
        """Test that violation is recorded for plain string hash."""
        service.validate_content_ref("plain_hash_value")
        violations = service.detect_violations()

        assert len(violations) == 1
        assert violations[0].violation_type == PatternViolationType.PLAIN_STRING_HASH


class ServiceWithHaltChecker:
    """Test service with halt checker attribute."""
    def __init__(self) -> None:
        self._halt_checker = object()


class ServiceWithoutHaltChecker:
    """Test service without halt checker attribute."""
    pass


class TestValidateHaltGuardInjection:
    """Tests for validate_halt_guard_injection method (PV-003)."""

    def test_valid_service_with_halt_checker(
        self, service: PatternViolationService
    ) -> None:
        """Test that services with halt checker are valid."""
        test_service = ServiceWithHaltChecker()
        is_valid = service.validate_halt_guard_injection(test_service)

        assert is_valid is True

    def test_invalid_service_without_halt_checker(
        self, service: PatternViolationService
    ) -> None:
        """Test that services without halt checker are invalid (PV-003)."""
        test_service = ServiceWithoutHaltChecker()
        is_valid = service.validate_halt_guard_injection(test_service)

        assert is_valid is False

    def test_records_violation_for_missing_halt_guard(
        self, service: PatternViolationService
    ) -> None:
        """Test that violation is recorded for missing HaltGuard."""
        test_service = ServiceWithoutHaltChecker()
        service.validate_halt_guard_injection(test_service)
        violations = service.detect_violations()

        assert len(violations) == 1
        assert violations[0].violation_type == PatternViolationType.MISSING_HALT_GUARD


class TestDetectViolations:
    """Tests for detect_violations method."""

    def test_returns_empty_list_when_no_violations(
        self, service: PatternViolationService
    ) -> None:
        """Test that empty list is returned when no violations."""
        violations = service.detect_violations()

        assert violations == []

    def test_returns_all_detected_violations(
        self, service: PatternViolationService
    ) -> None:
        """Test that all violations are returned."""
        service.validate_event_type("raw_string")
        service.validate_content_ref("plain_hash")

        violations = service.detect_violations()

        assert len(violations) == 2


class TestGetUnresolvedViolations:
    """Tests for get_unresolved_violations method."""

    def test_returns_only_unresolved(
        self, service: PatternViolationService
    ) -> None:
        """Test that only unresolved violations are returned."""
        service.validate_event_type("raw_string")
        violations = service.detect_violations()

        # Resolve the violation
        service.resolve_violation(str(violations[0].violation_id), "test_user")

        unresolved = service.get_unresolved_violations()

        assert len(unresolved) == 0


class TestGetBlockingViolations:
    """Tests for get_blocking_violations method."""

    def test_returns_blocking_violations(
        self, service: PatternViolationService
    ) -> None:
        """Test that blocking violations are returned."""
        # Create a critical violation
        service.validate_content_ref("plain_hash")  # PV-002 is critical

        blocking = service.get_blocking_violations()

        assert len(blocking) == 1
        assert blocking[0].blocks_deployment is True


class TestResolveViolation:
    """Tests for resolve_violation method."""

    def test_resolves_existing_violation(
        self, service: PatternViolationService
    ) -> None:
        """Test that existing violation can be resolved."""
        service.validate_event_type("raw_string")
        violations = service.detect_violations()

        result = service.resolve_violation(
            str(violations[0].violation_id),
            "test_user",
        )

        assert result is True
        assert violations[0].violation_id not in [
            v.violation_id for v in service.get_unresolved_violations()
        ]

    def test_returns_false_for_unknown_violation(
        self, service: PatternViolationService
    ) -> None:
        """Test that False is returned for unknown violation ID."""
        from uuid import uuid4

        result = service.resolve_violation(str(uuid4()), "test_user")

        assert result is False


class TestRaiseIfViolationsBlock:
    """Tests for raise_if_violations_block method."""

    def test_raises_when_blocking_violations_exist(
        self, service: PatternViolationService
    ) -> None:
        """Test that error is raised when blocking violations exist."""
        service.validate_content_ref("plain_hash")  # Critical violation

        with pytest.raises(FailureModeViolationError):
            service.raise_if_violations_block()

    def test_does_not_raise_when_no_violations(
        self, service: PatternViolationService
    ) -> None:
        """Test that no error is raised when no violations."""
        # Should not raise
        service.raise_if_violations_block()

    def test_does_not_raise_when_violations_resolved(
        self, service: PatternViolationService
    ) -> None:
        """Test that no error is raised when violations are resolved."""
        service.validate_event_type("raw_string")
        violations = service.detect_violations()
        service.resolve_violation(str(violations[0].violation_id), "test_user")

        # Should not raise
        service.raise_if_violations_block()


class TestCreateScanReport:
    """Tests for create_scan_report method."""

    def test_creates_scan_report(self, service: PatternViolationService) -> None:
        """Test that scan report is created."""
        service.validate_event_type("raw_string")

        scan = service.create_scan_report(
            files_scanned=100,
            scan_duration_ms=500,
        )

        assert scan.files_scanned == 100
        assert scan.scan_duration_ms == 500
        assert len(scan.violations) == 1

    def test_scan_report_includes_counts(
        self, service: PatternViolationService
    ) -> None:
        """Test that scan report includes violation counts."""
        service.validate_content_ref("plain_hash")  # Critical
        service.validate_event_type("raw_string")  # High

        scan = service.create_scan_report(
            files_scanned=50,
            scan_duration_ms=250,
        )

        assert scan.critical_count >= 1
        assert scan.blocking_count >= 1


class TestGetViolationStats:
    """Tests for get_violation_stats method."""

    def test_returns_stats(self, service: PatternViolationService) -> None:
        """Test that violation stats are returned."""
        stats = service.get_violation_stats()

        assert "total_violations" in stats
        assert "unresolved_count" in stats
        assert "blocking_count" in stats
        assert "by_type" in stats
        assert "by_severity" in stats

    def test_counts_by_type(self, service: PatternViolationService) -> None:
        """Test that violations are counted by type."""
        service.validate_event_type("raw_string1")
        service.validate_event_type("raw_string2")
        service.validate_content_ref("plain_hash")

        stats = service.get_violation_stats()

        assert stats["by_type"].get(PatternViolationType.RAW_STRING_EVENT_TYPE.value, 0) == 2
        assert stats["by_type"].get(PatternViolationType.PLAIN_STRING_HASH.value, 0) == 1


class TestGetViolationSummary:
    """Tests for get_violation_summary method."""

    def test_returns_clean_summary_when_no_violations(
        self, service: PatternViolationService
    ) -> None:
        """Test that clean summary is returned when no violations."""
        summary = service.get_violation_summary()

        assert "No pattern violations" in summary

    def test_returns_blocking_summary_when_critical(
        self, service: PatternViolationService
    ) -> None:
        """Test that blocking summary is returned for critical violations."""
        service.validate_content_ref("plain_hash")

        summary = service.get_violation_summary()

        assert "BLOCKING" in summary
