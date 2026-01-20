"""Chaos test report model for deliberation resilience testing.

Story 2B.8: Deliberation Chaos Testing (NFR-9.5)

This module defines the report structure for chaos test execution results,
capturing metrics about fault injection, recovery, and system behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class ChaosTestOutcome(Enum):
    """Outcome of a chaos test execution.

    Attributes:
        SUCCESS: System recovered fully from fault injection.
        FAILURE: System did not recover within timeout.
        PARTIAL_RECOVERY: Some but not all components/deliberations recovered.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_RECOVERY = "partial_recovery"


# Schema version for serialization compatibility
CHAOS_REPORT_SCHEMA_VERSION = 1

# NFR-10.6: Archon substitution latency threshold
ARCHON_SUBSTITUTION_SLA_MS = 10_000


@dataclass(frozen=True, eq=True)
class ChaosTestReport:
    """Report from a completed chaos test (Story 2B.8, NFR-9.5).

    Captures comprehensive metrics from chaos test execution including
    fault injection timing, recovery metrics, and affected deliberations.

    Attributes:
        test_id: Unique identifier for this test run.
        scenario: The scenario that was executed.
        config: The ChaosTestConfig used (serialized).
        started_at: When the test started (UTC).
        completed_at: When the test finished (UTC).
        injection_started_at: When fault injection began.
        injection_ended_at: When fault injection ended.
        recovery_detected_at: When system recovery was detected (None if not recovered).
        outcome: SUCCESS, FAILURE, or PARTIAL_RECOVERY.
        deliberations_affected: Count of deliberations impacted.
        deliberations_recovered: Count that successfully recovered.
        deliberations_failed: Count that failed due to chaos.
        witness_chain_intact: Boolean indicating witness integrity (CT-12).
        audit_log_entries: List of audit events during test.
        failure_details: If failed, details of what went wrong.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> report = ChaosTestReport(
        ...     test_id=uuid4(),
        ...     scenario="archon_timeout_mid_phase",
        ...     config={},
        ...     started_at=datetime.now(timezone.utc),
        ...     completed_at=datetime.now(timezone.utc),
        ...     injection_started_at=datetime.now(timezone.utc),
        ...     injection_ended_at=datetime.now(timezone.utc),
        ...     recovery_detected_at=datetime.now(timezone.utc),
        ...     outcome=ChaosTestOutcome.SUCCESS,
        ...     deliberations_affected=10,
        ...     deliberations_recovered=10,
        ...     deliberations_failed=0,
        ... )
        >>> report.outcome == ChaosTestOutcome.SUCCESS
        True
    """

    test_id: UUID
    scenario: str
    config: dict[str, Any]
    started_at: datetime
    completed_at: datetime
    injection_started_at: datetime
    injection_ended_at: datetime
    recovery_detected_at: datetime | None
    outcome: ChaosTestOutcome
    deliberations_affected: int
    deliberations_recovered: int
    deliberations_failed: int
    witness_chain_intact: bool = field(default=True)
    audit_log_entries: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    failure_details: str | None = field(default=None)

    @property
    def recovery_duration_ms(self) -> float | None:
        """Get recovery duration in milliseconds.

        Returns:
            Time from injection end to recovery detection, or None if not recovered.
        """
        if self.recovery_detected_at is None:
            return None
        return (
            self.recovery_detected_at - self.injection_ended_at
        ).total_seconds() * 1000

    @property
    def injection_duration_ms(self) -> float:
        """Get fault injection duration in milliseconds.

        Returns:
            Duration of fault injection.
        """
        return (
            self.injection_ended_at - self.injection_started_at
        ).total_seconds() * 1000

    @property
    def total_duration_seconds(self) -> float:
        """Get total test duration in seconds.

        Returns:
            Total time from test start to completion.
        """
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def recovery_rate(self) -> float:
        """Get recovery rate as percentage.

        Returns:
            Percentage of affected deliberations that recovered (0-100).
        """
        if self.deliberations_affected == 0:
            return 100.0
        return (self.deliberations_recovered / self.deliberations_affected) * 100

    @property
    def nfr_10_6_pass(self) -> bool:
        """Check if NFR-10.6 (archon substitution < 10s) is satisfied.

        Returns:
            True if recovery was within SLA, False otherwise.
        """
        if self.recovery_duration_ms is None:
            return False
        return self.recovery_duration_ms < ARCHON_SUBSTITUTION_SLA_MS

    def summary(self) -> str:
        """Generate human-readable summary.

        Returns:
            Multi-line string summarizing the test results.
        """
        recovery_str = (
            f"{self.recovery_duration_ms:.0f}ms" if self.recovery_duration_ms else "N/A"
        )
        witness_str = "INTACT" if self.witness_chain_intact else "BROKEN"
        nfr_str = "PASS" if self.nfr_10_6_pass else "FAIL"
        return (
            f"Chaos Test Report ({self.test_id})\n"
            f"{'=' * 50}\n"
            f"Scenario: {self.scenario}\n"
            f"Outcome: {self.outcome.value.upper()}\n"
            f"Duration: {self.total_duration_seconds:.1f}s\n"
            f"Fault Injection: {self.injection_duration_ms:.0f}ms\n"
            f"Recovery Time: {recovery_str}\n"
            f"Deliberations:\n"
            f"  - Affected: {self.deliberations_affected}\n"
            f"  - Recovered: {self.deliberations_recovered}\n"
            f"  - Failed: {self.deliberations_failed}\n"
            f"  - Recovery Rate: {self.recovery_rate:.1f}%\n"
            f"Witness Chain: {witness_str}\n"
            f"NFR-10.6 (< 10s substitution): {nfr_str}\n"
            f"Audit Log Entries: {len(self.audit_log_entries)}\n"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "test_id": str(self.test_id),
            "scenario": self.scenario,
            "config": self.config,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "injection_started_at": self.injection_started_at.isoformat(),
            "injection_ended_at": self.injection_ended_at.isoformat(),
            "recovery_detected_at": (
                self.recovery_detected_at.isoformat()
                if self.recovery_detected_at
                else None
            ),
            "recovery_duration_ms": self.recovery_duration_ms,
            "injection_duration_ms": self.injection_duration_ms,
            "total_duration_seconds": self.total_duration_seconds,
            "outcome": self.outcome.value,
            "deliberations_affected": self.deliberations_affected,
            "deliberations_recovered": self.deliberations_recovered,
            "deliberations_failed": self.deliberations_failed,
            "recovery_rate": self.recovery_rate,
            "witness_chain_intact": self.witness_chain_intact,
            "audit_log_entries": list(self.audit_log_entries),
            "failure_details": self.failure_details,
            "nfr_10_6_pass": self.nfr_10_6_pass,
            "schema_version": CHAOS_REPORT_SCHEMA_VERSION,
        }
