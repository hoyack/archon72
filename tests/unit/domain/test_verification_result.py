"""Unit tests for verification result models (Story 8.5, FR146, NFR35).

Tests for:
- VerificationCheck construction and validation
- VerificationResult construction and validation
- VerificationStatus enum values
- Helper methods and properties
"""

from datetime import datetime, timezone, timedelta

import pytest

from src.domain.models.verification_result import (
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)


class TestVerificationStatus:
    """Tests for VerificationStatus enum."""

    def test_has_passed_status(self) -> None:
        """VerificationStatus should have PASSED value."""
        assert VerificationStatus.PASSED.value == "passed"

    def test_has_failed_status(self) -> None:
        """VerificationStatus should have FAILED value."""
        assert VerificationStatus.FAILED.value == "failed"

    def test_has_bypassed_status(self) -> None:
        """VerificationStatus should have BYPASSED value."""
        assert VerificationStatus.BYPASSED.value == "bypassed"


class TestVerificationCheck:
    """Tests for VerificationCheck dataclass."""

    def test_create_passing_check(self) -> None:
        """Should create a passing check successfully."""
        check = VerificationCheck(
            name="hash_chain",
            passed=True,
            details="Verified 1000 events",
            duration_ms=150.5,
        )
        assert check.name == "hash_chain"
        assert check.passed is True
        assert check.details == "Verified 1000 events"
        assert check.duration_ms == 150.5
        assert check.error_code is None

    def test_create_failing_check_with_error_code(self) -> None:
        """Should create a failing check with explicit error code."""
        check = VerificationCheck(
            name="witness_pool",
            passed=False,
            details="Pool has 4 witnesses (minimum: 6)",
            duration_ms=50.0,
            error_code="witness_pool_insufficient",
        )
        assert check.name == "witness_pool"
        assert check.passed is False
        assert check.error_code == "witness_pool_insufficient"

    def test_create_failing_check_generates_default_error_code(self) -> None:
        """Should generate default error code for failing check."""
        check = VerificationCheck(
            name="keeper_keys",
            passed=False,
            details="No active keys found",
            duration_ms=25.0,
        )
        assert check.error_code == "keeper_keys_failed"

    def test_create_check_with_metadata(self) -> None:
        """Should create check with metadata dict."""
        check = VerificationCheck(
            name="replica_sync",
            passed=True,
            details="All replicas in sync",
            duration_ms=100.0,
            metadata={"replica_count": 3, "lag_ms": 50},
        )
        assert check.metadata == {"replica_count": 3, "lag_ms": 50}

    def test_empty_name_raises_error(self) -> None:
        """Should raise error for empty name."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            VerificationCheck(
                name="",
                passed=True,
                details="Test",
                duration_ms=10.0,
            )

    def test_negative_duration_raises_error(self) -> None:
        """Should raise error for negative duration."""
        with pytest.raises(ValueError, match="duration_ms must be non-negative"):
            VerificationCheck(
                name="test",
                passed=True,
                details="Test",
                duration_ms=-5.0,
            )

    def test_check_is_frozen(self) -> None:
        """Check should be immutable (frozen)."""
        check = VerificationCheck(
            name="test",
            passed=True,
            details="Test",
            duration_ms=10.0,
        )
        with pytest.raises(AttributeError):
            check.name = "modified"  # type: ignore


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_create_passed_result(self) -> None:
        """Should create a passed result."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=200)
        checks = (
            VerificationCheck("hash_chain", True, "OK", 50.0),
            VerificationCheck("witness_pool", True, "OK", 50.0),
        )

        result = VerificationResult(
            status=VerificationStatus.PASSED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        assert result.status == VerificationStatus.PASSED
        assert len(result.checks) == 2
        assert result.is_post_halt is False
        assert result.bypass_reason is None
        assert result.bypass_count == 0

    def test_create_failed_result(self) -> None:
        """Should create a failed result."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=300)
        checks = (
            VerificationCheck("hash_chain", True, "OK", 50.0),
            VerificationCheck("witness_pool", False, "Failed", 50.0, "witness_pool_insufficient"),
        )

        result = VerificationResult(
            status=VerificationStatus.FAILED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        assert result.status == VerificationStatus.FAILED
        assert result.failure_count == 1

    def test_create_bypassed_result_requires_reason(self) -> None:
        """Should require bypass_reason when status is BYPASSED."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=100)
        checks = (VerificationCheck("hash_chain", False, "Failed", 50.0, "hash_chain_corrupted"),)

        with pytest.raises(ValueError, match="bypass_reason required"):
            VerificationResult(
                status=VerificationStatus.BYPASSED,
                checks=checks,
                started_at=started,
                completed_at=completed,
            )

    def test_create_bypassed_result_with_reason(self) -> None:
        """Should create bypassed result with reason."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=100)
        checks = (VerificationCheck("hash_chain", False, "Failed", 50.0, "hash_chain_corrupted"),)

        result = VerificationResult(
            status=VerificationStatus.BYPASSED,
            checks=checks,
            started_at=started,
            completed_at=completed,
            bypass_reason="Continuous restart bypass",
            bypass_count=2,
        )

        assert result.status == VerificationStatus.BYPASSED
        assert result.bypass_reason == "Continuous restart bypass"
        assert result.bypass_count == 2

    def test_completed_before_started_raises_error(self) -> None:
        """Should raise error if completed_at is before started_at."""
        started = datetime.now(timezone.utc)
        completed = started - timedelta(seconds=1)  # Before started
        checks = (VerificationCheck("test", True, "OK", 50.0),)

        with pytest.raises(ValueError, match="completed_at cannot be before started_at"):
            VerificationResult(
                status=VerificationStatus.PASSED,
                checks=checks,
                started_at=started,
                completed_at=completed,
            )

    def test_negative_bypass_count_raises_error(self) -> None:
        """Should raise error for negative bypass_count."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=100)
        checks = (VerificationCheck("test", False, "Failed", 50.0, "test_failed"),)

        with pytest.raises(ValueError, match="bypass_count must be non-negative"):
            VerificationResult(
                status=VerificationStatus.BYPASSED,
                checks=checks,
                started_at=started,
                completed_at=completed,
                bypass_reason="Test bypass",
                bypass_count=-1,
            )

    def test_failed_checks_property(self) -> None:
        """Should return only failed checks."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=200)
        checks = (
            VerificationCheck("hash_chain", True, "OK", 50.0),
            VerificationCheck("witness_pool", False, "Failed", 50.0, "witness_pool_insufficient"),
            VerificationCheck("keeper_keys", False, "Failed", 50.0, "keeper_keys_failed"),
        )

        result = VerificationResult(
            status=VerificationStatus.FAILED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        failed = result.failed_checks
        assert len(failed) == 2
        assert failed[0].name == "witness_pool"
        assert failed[1].name == "keeper_keys"

    def test_passed_checks_property(self) -> None:
        """Should return only passed checks."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=200)
        checks = (
            VerificationCheck("hash_chain", True, "OK", 50.0),
            VerificationCheck("witness_pool", False, "Failed", 50.0, "witness_pool_insufficient"),
            VerificationCheck("checkpoint", True, "OK", 50.0),
        )

        result = VerificationResult(
            status=VerificationStatus.FAILED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        passed = result.passed_checks
        assert len(passed) == 2
        assert passed[0].name == "hash_chain"
        assert passed[1].name == "checkpoint"

    def test_duration_ms_property(self) -> None:
        """Should calculate duration in milliseconds."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=250)
        checks = (VerificationCheck("test", True, "OK", 50.0),)

        result = VerificationResult(
            status=VerificationStatus.PASSED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        # Allow for floating point imprecision
        assert 249.0 <= result.duration_ms <= 251.0

    def test_check_count_property(self) -> None:
        """Should return total check count."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=100)
        checks = (
            VerificationCheck("check1", True, "OK", 10.0),
            VerificationCheck("check2", True, "OK", 10.0),
            VerificationCheck("check3", False, "Failed", 10.0, "check3_failed"),
        )

        result = VerificationResult(
            status=VerificationStatus.FAILED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        assert result.check_count == 3

    def test_failure_count_property(self) -> None:
        """Should return count of failed checks."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=100)
        checks = (
            VerificationCheck("check1", True, "OK", 10.0),
            VerificationCheck("check2", False, "Failed", 10.0, "check2_failed"),
            VerificationCheck("check3", False, "Failed", 10.0, "check3_failed"),
        )

        result = VerificationResult(
            status=VerificationStatus.FAILED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        assert result.failure_count == 2

    def test_get_check_by_name_found(self) -> None:
        """Should return check when found by name."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=100)
        checks = (
            VerificationCheck("hash_chain", True, "OK", 50.0),
            VerificationCheck("witness_pool", True, "OK", 30.0),
        )

        result = VerificationResult(
            status=VerificationStatus.PASSED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        check = result.get_check_by_name("witness_pool")
        assert check is not None
        assert check.name == "witness_pool"

    def test_get_check_by_name_not_found(self) -> None:
        """Should return None when check not found."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=100)
        checks = (VerificationCheck("hash_chain", True, "OK", 50.0),)

        result = VerificationResult(
            status=VerificationStatus.PASSED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        check = result.get_check_by_name("nonexistent")
        assert check is None

    def test_to_summary_passed(self) -> None:
        """Should generate summary for passed result."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=150)
        checks = (
            VerificationCheck("hash_chain", True, "OK", 50.0),
            VerificationCheck("witness_pool", True, "OK", 50.0),
        )

        result = VerificationResult(
            status=VerificationStatus.PASSED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        summary = result.to_summary()
        assert "PASSED" in summary
        assert "2/2 passed" in summary

    def test_to_summary_failed(self) -> None:
        """Should generate summary for failed result with details."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=150)
        checks = (
            VerificationCheck("hash_chain", True, "OK", 50.0),
            VerificationCheck("witness_pool", False, "Pool too small", 50.0, "witness_pool_insufficient"),
        )

        result = VerificationResult(
            status=VerificationStatus.FAILED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        summary = result.to_summary()
        assert "FAILED" in summary
        assert "1/2 passed" in summary
        assert "Failed checks:" in summary
        assert "witness_pool" in summary
        assert "Pool too small" in summary

    def test_to_summary_bypassed(self) -> None:
        """Should generate summary for bypassed result."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=150)
        checks = (
            VerificationCheck("hash_chain", False, "Corrupted", 50.0, "hash_chain_corrupted"),
        )

        result = VerificationResult(
            status=VerificationStatus.BYPASSED,
            checks=checks,
            started_at=started,
            completed_at=completed,
            bypass_reason="Continuous restart",
            bypass_count=2,
        )

        summary = result.to_summary()
        assert "BYPASSED" in summary
        assert "Bypass:" in summary
        assert "Continuous restart" in summary
        assert "count: 2" in summary

    def test_to_summary_post_halt(self) -> None:
        """Should indicate post-halt mode in summary."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=150)
        checks = (VerificationCheck("hash_chain", True, "OK", 50.0),)

        result = VerificationResult(
            status=VerificationStatus.PASSED,
            checks=checks,
            started_at=started,
            completed_at=completed,
            is_post_halt=True,
        )

        summary = result.to_summary()
        assert "Post-Halt Recovery" in summary
        assert "stringent" in summary

    def test_result_is_frozen(self) -> None:
        """Result should be immutable (frozen)."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(milliseconds=100)
        checks = (VerificationCheck("test", True, "OK", 50.0),)

        result = VerificationResult(
            status=VerificationStatus.PASSED,
            checks=checks,
            started_at=started,
            completed_at=completed,
        )

        with pytest.raises(AttributeError):
            result.status = VerificationStatus.FAILED  # type: ignore
