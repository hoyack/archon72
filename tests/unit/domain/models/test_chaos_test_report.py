"""Unit tests for ChaosTestReport domain model (Story 2B.8, NFR-9.5).

Tests:
- Report creation with all fields
- Computed properties (recovery_duration_ms, recovery_rate, etc.)
- Summary generation
- Serialization to dict
- NFR-10.6 compliance check
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.domain.models.chaos_test_report import (
    ARCHON_SUBSTITUTION_SLA_MS,
    CHAOS_REPORT_SCHEMA_VERSION,
    ChaosTestOutcome,
    ChaosTestReport,
)


def create_test_report(
    outcome: ChaosTestOutcome = ChaosTestOutcome.SUCCESS,
    deliberations_affected: int = 10,
    deliberations_recovered: int = 10,
    deliberations_failed: int = 0,
    recovery_duration_ms: float = 5000.0,
    witness_chain_intact: bool = True,
) -> ChaosTestReport:
    """Create a test report with configurable parameters."""
    started_at = datetime.now(timezone.utc)
    injection_started_at = started_at + timedelta(milliseconds=100)
    injection_ended_at = injection_started_at + timedelta(seconds=30)
    recovery_detected_at = injection_ended_at + timedelta(
        milliseconds=recovery_duration_ms
    )
    completed_at = recovery_detected_at + timedelta(milliseconds=100)

    return ChaosTestReport(
        test_id=uuid4(),
        scenario="archon_timeout_mid_phase",
        config={"scenario": "archon_timeout_mid_phase"},
        started_at=started_at,
        completed_at=completed_at,
        injection_started_at=injection_started_at,
        injection_ended_at=injection_ended_at,
        recovery_detected_at=recovery_detected_at,
        outcome=outcome,
        deliberations_affected=deliberations_affected,
        deliberations_recovered=deliberations_recovered,
        deliberations_failed=deliberations_failed,
        witness_chain_intact=witness_chain_intact,
        audit_log_entries=({"event": "test"},),
        failure_details=None if outcome == ChaosTestOutcome.SUCCESS else "Test failure",
    )


class TestChaosTestOutcomeEnumeration:
    """Test ChaosTestOutcome enumeration."""

    def test_all_outcomes_exist(self) -> None:
        """All expected outcomes are defined."""
        assert ChaosTestOutcome.SUCCESS
        assert ChaosTestOutcome.FAILURE
        assert ChaosTestOutcome.PARTIAL_RECOVERY

    def test_outcome_count(self) -> None:
        """Three outcomes are defined."""
        assert len(ChaosTestOutcome) == 3

    def test_outcome_values(self) -> None:
        """Outcome values are lowercase strings."""
        assert ChaosTestOutcome.SUCCESS.value == "success"
        assert ChaosTestOutcome.FAILURE.value == "failure"
        assert ChaosTestOutcome.PARTIAL_RECOVERY.value == "partial_recovery"


class TestChaosTestReportCreation:
    """Test ChaosTestReport creation."""

    def test_basic_report_creation(self) -> None:
        """Report can be created with required fields."""
        report = create_test_report()

        assert report.scenario == "archon_timeout_mid_phase"
        assert report.outcome == ChaosTestOutcome.SUCCESS
        assert report.deliberations_affected == 10
        assert report.deliberations_recovered == 10
        assert report.deliberations_failed == 0
        assert report.witness_chain_intact is True

    def test_report_with_failure_details(self) -> None:
        """Report includes failure details when present."""
        report = create_test_report(
            outcome=ChaosTestOutcome.FAILURE,
            deliberations_recovered=0,
            deliberations_failed=10,
        )

        assert report.outcome == ChaosTestOutcome.FAILURE
        assert report.failure_details == "Test failure"

    def test_report_with_no_recovery(self) -> None:
        """Report handles no recovery (None recovery_detected_at)."""
        started_at = datetime.now(timezone.utc)
        injection_started_at = started_at
        injection_ended_at = started_at + timedelta(seconds=30)
        completed_at = started_at + timedelta(seconds=60)

        report = ChaosTestReport(
            test_id=uuid4(),
            scenario="service_restart",
            config={},
            started_at=started_at,
            completed_at=completed_at,
            injection_started_at=injection_started_at,
            injection_ended_at=injection_ended_at,
            recovery_detected_at=None,  # No recovery
            outcome=ChaosTestOutcome.FAILURE,
            deliberations_affected=5,
            deliberations_recovered=0,
            deliberations_failed=5,
        )

        assert report.recovery_detected_at is None
        assert report.recovery_duration_ms is None


class TestChaosTestReportComputedProperties:
    """Test ChaosTestReport computed properties."""

    def test_recovery_duration_ms(self) -> None:
        """recovery_duration_ms calculates correctly."""
        report = create_test_report(recovery_duration_ms=5000.0)

        # Allow some tolerance for timing
        assert report.recovery_duration_ms is not None
        assert 4900.0 <= report.recovery_duration_ms <= 5100.0

    def test_recovery_duration_ms_when_no_recovery(self) -> None:
        """recovery_duration_ms returns None when no recovery."""
        started_at = datetime.now(timezone.utc)
        report = ChaosTestReport(
            test_id=uuid4(),
            scenario="test",
            config={},
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=60),
            injection_started_at=started_at,
            injection_ended_at=started_at + timedelta(seconds=30),
            recovery_detected_at=None,
            outcome=ChaosTestOutcome.FAILURE,
            deliberations_affected=0,
            deliberations_recovered=0,
            deliberations_failed=0,
        )

        assert report.recovery_duration_ms is None

    def test_injection_duration_ms(self) -> None:
        """injection_duration_ms calculates correctly."""
        started_at = datetime.now(timezone.utc)
        injection_started_at = started_at
        injection_ended_at = started_at + timedelta(milliseconds=30000)  # 30 seconds

        report = ChaosTestReport(
            test_id=uuid4(),
            scenario="test",
            config={},
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=60),
            injection_started_at=injection_started_at,
            injection_ended_at=injection_ended_at,
            recovery_detected_at=injection_ended_at + timedelta(milliseconds=100),
            outcome=ChaosTestOutcome.SUCCESS,
            deliberations_affected=0,
            deliberations_recovered=0,
            deliberations_failed=0,
        )

        assert 29900.0 <= report.injection_duration_ms <= 30100.0

    def test_total_duration_seconds(self) -> None:
        """total_duration_seconds calculates correctly."""
        started_at = datetime.now(timezone.utc)
        completed_at = started_at + timedelta(seconds=120)

        report = ChaosTestReport(
            test_id=uuid4(),
            scenario="test",
            config={},
            started_at=started_at,
            completed_at=completed_at,
            injection_started_at=started_at,
            injection_ended_at=started_at + timedelta(seconds=30),
            recovery_detected_at=started_at + timedelta(seconds=35),
            outcome=ChaosTestOutcome.SUCCESS,
            deliberations_affected=0,
            deliberations_recovered=0,
            deliberations_failed=0,
        )

        assert report.total_duration_seconds == 120.0

    def test_recovery_rate_full_recovery(self) -> None:
        """recovery_rate is 100% for full recovery."""
        report = create_test_report(
            deliberations_affected=10,
            deliberations_recovered=10,
            deliberations_failed=0,
        )

        assert report.recovery_rate == 100.0

    def test_recovery_rate_partial_recovery(self) -> None:
        """recovery_rate calculates correctly for partial recovery."""
        report = create_test_report(
            deliberations_affected=10,
            deliberations_recovered=8,
            deliberations_failed=2,
        )

        assert report.recovery_rate == 80.0

    def test_recovery_rate_no_recovery(self) -> None:
        """recovery_rate is 0% when no deliberations recover."""
        report = create_test_report(
            deliberations_affected=10,
            deliberations_recovered=0,
            deliberations_failed=10,
        )

        assert report.recovery_rate == 0.0

    def test_recovery_rate_no_affected(self) -> None:
        """recovery_rate is 100% when no deliberations were affected."""
        report = create_test_report(
            deliberations_affected=0,
            deliberations_recovered=0,
            deliberations_failed=0,
        )

        assert report.recovery_rate == 100.0


class TestChaosTestReportNFRCompliance:
    """Test NFR-10.6 compliance checking."""

    def test_nfr_10_6_pass_under_threshold(self) -> None:
        """nfr_10_6_pass is True when recovery under 10s."""
        report = create_test_report(recovery_duration_ms=5000.0)

        assert report.nfr_10_6_pass is True

    def test_nfr_10_6_fail_over_threshold(self) -> None:
        """nfr_10_6_pass is False when recovery over 10s."""
        report = create_test_report(recovery_duration_ms=15000.0)

        assert report.nfr_10_6_pass is False

    def test_nfr_10_6_boundary_at_threshold(self) -> None:
        """nfr_10_6_pass is False at exactly 10s (must be strictly less)."""
        report = create_test_report(recovery_duration_ms=ARCHON_SUBSTITUTION_SLA_MS)

        assert report.nfr_10_6_pass is False

    def test_nfr_10_6_fail_no_recovery(self) -> None:
        """nfr_10_6_pass is False when no recovery occurred."""
        started_at = datetime.now(timezone.utc)
        report = ChaosTestReport(
            test_id=uuid4(),
            scenario="test",
            config={},
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=60),
            injection_started_at=started_at,
            injection_ended_at=started_at + timedelta(seconds=30),
            recovery_detected_at=None,
            outcome=ChaosTestOutcome.FAILURE,
            deliberations_affected=5,
            deliberations_recovered=0,
            deliberations_failed=5,
        )

        assert report.nfr_10_6_pass is False


class TestChaosTestReportSummary:
    """Test ChaosTestReport summary generation."""

    def test_summary_includes_key_information(self) -> None:
        """Summary includes all key report information."""
        report = create_test_report()
        summary = report.summary()

        assert "Chaos Test Report" in summary
        assert str(report.test_id) in summary
        assert "archon_timeout_mid_phase" in summary
        assert "SUCCESS" in summary
        assert "Deliberations:" in summary
        assert "Affected: 10" in summary
        assert "Recovered: 10" in summary
        assert "Failed: 0" in summary
        assert "Recovery Rate: 100.0%" in summary
        assert "Witness Chain: INTACT" in summary
        assert "NFR-10.6" in summary

    def test_summary_shows_broken_witness_chain(self) -> None:
        """Summary shows BROKEN when witness chain is compromised."""
        report = create_test_report(witness_chain_intact=False)
        summary = report.summary()

        assert "Witness Chain: BROKEN" in summary

    def test_summary_shows_nfr_fail(self) -> None:
        """Summary shows FAIL when NFR-10.6 is not met."""
        report = create_test_report(recovery_duration_ms=15000.0)
        summary = report.summary()

        assert "FAIL" in summary


class TestChaosTestReportSerialization:
    """Test ChaosTestReport serialization."""

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all report fields."""
        report = create_test_report()
        result = report.to_dict()

        assert result["test_id"] == str(report.test_id)
        assert result["scenario"] == "archon_timeout_mid_phase"
        assert result["config"] == {"scenario": "archon_timeout_mid_phase"}
        assert "started_at" in result
        assert "completed_at" in result
        assert "injection_started_at" in result
        assert "injection_ended_at" in result
        assert "recovery_detected_at" in result
        assert result["outcome"] == "success"
        assert result["deliberations_affected"] == 10
        assert result["deliberations_recovered"] == 10
        assert result["deliberations_failed"] == 0
        assert result["recovery_rate"] == 100.0
        assert result["witness_chain_intact"] is True
        assert result["audit_log_entries"] == [{"event": "test"}]
        assert result["failure_details"] is None
        assert result["nfr_10_6_pass"] is True
        assert result["schema_version"] == CHAOS_REPORT_SCHEMA_VERSION

    def test_to_dict_handles_none_recovery(self) -> None:
        """to_dict handles None recovery_detected_at."""
        started_at = datetime.now(timezone.utc)
        report = ChaosTestReport(
            test_id=uuid4(),
            scenario="test",
            config={},
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=60),
            injection_started_at=started_at,
            injection_ended_at=started_at + timedelta(seconds=30),
            recovery_detected_at=None,
            outcome=ChaosTestOutcome.FAILURE,
            deliberations_affected=0,
            deliberations_recovered=0,
            deliberations_failed=0,
        )

        result = report.to_dict()

        assert result["recovery_detected_at"] is None
        assert result["recovery_duration_ms"] is None


class TestChaosTestReportEquality:
    """Test ChaosTestReport equality."""

    def test_same_test_id_same_values_are_equal(self) -> None:
        """Reports with same values are equal."""
        test_id = uuid4()
        started_at = datetime.now(timezone.utc)
        completed_at = started_at + timedelta(seconds=60)
        injection_started_at = started_at
        injection_ended_at = started_at + timedelta(seconds=30)
        recovery_detected_at = started_at + timedelta(seconds=35)

        report1 = ChaosTestReport(
            test_id=test_id,
            scenario="test",
            config={},
            started_at=started_at,
            completed_at=completed_at,
            injection_started_at=injection_started_at,
            injection_ended_at=injection_ended_at,
            recovery_detected_at=recovery_detected_at,
            outcome=ChaosTestOutcome.SUCCESS,
            deliberations_affected=10,
            deliberations_recovered=10,
            deliberations_failed=0,
        )

        report2 = ChaosTestReport(
            test_id=test_id,
            scenario="test",
            config={},
            started_at=started_at,
            completed_at=completed_at,
            injection_started_at=injection_started_at,
            injection_ended_at=injection_ended_at,
            recovery_detected_at=recovery_detected_at,
            outcome=ChaosTestOutcome.SUCCESS,
            deliberations_affected=10,
            deliberations_recovered=10,
            deliberations_failed=0,
        )

        assert report1 == report2

    def test_different_test_ids_are_not_equal(self) -> None:
        """Reports with different test_ids are not equal."""
        started_at = datetime.now(timezone.utc)

        report1 = ChaosTestReport(
            test_id=uuid4(),
            scenario="test",
            config={},
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=60),
            injection_started_at=started_at,
            injection_ended_at=started_at + timedelta(seconds=30),
            recovery_detected_at=started_at + timedelta(seconds=35),
            outcome=ChaosTestOutcome.SUCCESS,
            deliberations_affected=10,
            deliberations_recovered=10,
            deliberations_failed=0,
        )

        report2 = ChaosTestReport(
            test_id=uuid4(),
            scenario="test",
            config={},
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=60),
            injection_started_at=started_at,
            injection_ended_at=started_at + timedelta(seconds=30),
            recovery_detected_at=started_at + timedelta(seconds=35),
            outcome=ChaosTestOutcome.SUCCESS,
            deliberations_affected=10,
            deliberations_recovered=10,
            deliberations_failed=0,
        )

        assert report1 != report2
