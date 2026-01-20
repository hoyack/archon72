"""Stub implementation of ChaosTestHarnessProtocol for testing.

Story 2B.8: Deliberation Chaos Testing (NFR-9.5)

This stub simulates chaos test execution with configurable behavior
for fast unit and integration tests.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.chaos_test_harness import FaultHandle
from src.domain.models.chaos_test_config import ChaosScenario, ChaosTestConfig
from src.domain.models.chaos_test_report import ChaosTestOutcome, ChaosTestReport


class ChaosTestHarnessStub:
    """Stub implementation of ChaosTestHarnessProtocol for testing.

    Simulates chaos test execution with configurable behavior for fast
    unit and integration tests. Provides full protocol compliance with
    configurable outcomes and timing.

    Default scenario outcomes simulate realistic recovery patterns:
    - Most scenarios recover fully (SUCCESS)
    - WITNESS_WRITE_FAILURE shows partial recovery (demonstrates graceful degradation)

    Attributes:
        base_recovery_ms: Base simulated recovery time in milliseconds.
        recovery_variance_ms: Random variance applied to recovery time.

    Example:
        >>> stub = ChaosTestHarnessStub()
        >>> config = ChaosTestConfig(
        ...     scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
        ... )
        >>> report = await stub.run_chaos_test(config)
        >>> assert report.outcome == ChaosTestOutcome.SUCCESS
    """

    # Default outcomes per scenario - simulate realistic recovery behavior
    SCENARIO_OUTCOMES: dict[ChaosScenario, ChaosTestOutcome] = {
        ChaosScenario.ARCHON_TIMEOUT_MID_PHASE: ChaosTestOutcome.SUCCESS,
        ChaosScenario.SERVICE_RESTART: ChaosTestOutcome.SUCCESS,
        ChaosScenario.DATABASE_CONNECTION_FAILURE: ChaosTestOutcome.SUCCESS,
        ChaosScenario.CREWAI_API_DEGRADATION: ChaosTestOutcome.SUCCESS,
        ChaosScenario.WITNESS_WRITE_FAILURE: ChaosTestOutcome.PARTIAL_RECOVERY,
        ChaosScenario.NETWORK_PARTITION: ChaosTestOutcome.SUCCESS,
    }

    # Component mapping for scenarios
    SCENARIO_COMPONENTS: dict[ChaosScenario, tuple[str, ...]] = {
        ChaosScenario.ARCHON_TIMEOUT_MID_PHASE: ("archon_pool", "deliberation_service"),
        ChaosScenario.SERVICE_RESTART: ("deliberation_service",),
        ChaosScenario.DATABASE_CONNECTION_FAILURE: ("postgres", "connection_pool"),
        ChaosScenario.CREWAI_API_DEGRADATION: ("crewai_adapter",),
        ChaosScenario.WITNESS_WRITE_FAILURE: ("event_writer", "witness_service"),
        ChaosScenario.NETWORK_PARTITION: ("network", "all_components"),
    }

    def __init__(
        self,
        base_recovery_ms: float = 100.0,
        recovery_variance_ms: float = 50.0,
    ) -> None:
        """Initialize stub with configurable recovery timing.

        Args:
            base_recovery_ms: Base simulated recovery time in milliseconds.
            recovery_variance_ms: Random variance applied to recovery time.
        """
        self._active_faults: dict[UUID, FaultHandle] = {}
        self._test_history: list[dict[str, Any]] = []
        self._inject_calls: list[dict[str, Any]] = []
        self._remove_calls: list[dict[str, Any]] = []
        self._base_recovery_ms = base_recovery_ms
        self._recovery_variance_ms = recovery_variance_ms
        self._forced_outcome: ChaosTestOutcome | None = None
        self._forced_recovery_ms: float | None = None
        self._forced_deliberations_affected: int | None = None
        self._forced_witness_chain_intact: bool | None = None

    async def run_chaos_test(
        self,
        config: ChaosTestConfig,
    ) -> ChaosTestReport:
        """Simulate chaos test execution.

        Args:
            config: Chaos test configuration.

        Returns:
            ChaosTestReport with simulated metrics.
        """
        started_at = datetime.now(timezone.utc)

        # Record test run
        self._test_history.append(
            {
                "config": config,
                "timestamp": started_at,
            }
        )

        # Simulate fault injection timing
        injection_started_at = started_at

        # Simulate injection duration (scaled down for testing)
        await asyncio.sleep(0.01)

        injection_ended_at = datetime.now(timezone.utc)

        # Simulate recovery
        recovery_ms = self._forced_recovery_ms or self._generate_recovery_time()
        await asyncio.sleep(recovery_ms / 10000)  # Scale down for testing

        recovery_detected_at = datetime.now(timezone.utc)
        completed_at = datetime.now(timezone.utc)

        # Determine outcome
        outcome = self._forced_outcome or self.SCENARIO_OUTCOMES.get(
            config.scenario, ChaosTestOutcome.SUCCESS
        )

        # Simulate affected deliberations
        deliberations_affected = (
            self._forced_deliberations_affected
            if self._forced_deliberations_affected is not None
            else random.randint(5, 20)
        )

        if outcome == ChaosTestOutcome.SUCCESS:
            deliberations_recovered = deliberations_affected
            deliberations_failed = 0
        elif outcome == ChaosTestOutcome.PARTIAL_RECOVERY:
            deliberations_recovered = int(deliberations_affected * 0.8)
            deliberations_failed = deliberations_affected - deliberations_recovered
        else:
            deliberations_recovered = 0
            deliberations_failed = deliberations_affected

        # Determine witness chain integrity
        witness_chain_intact = (
            self._forced_witness_chain_intact
            if self._forced_witness_chain_intact is not None
            else (outcome != ChaosTestOutcome.FAILURE)
        )

        # Generate audit log entries
        audit_entries = self._generate_audit_entries(
            config.scenario,
            injection_started_at,
            injection_ended_at,
            recovery_detected_at,
        )

        return ChaosTestReport(
            test_id=uuid4(),
            scenario=config.scenario.value,
            config=config.to_dict(),
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
            audit_log_entries=tuple(audit_entries),
            failure_details=None
            if outcome == ChaosTestOutcome.SUCCESS
            else "Simulated failure",
        )

    async def inject_fault(
        self,
        scenario: ChaosScenario,
        affected_components: tuple[str, ...] | None = None,
    ) -> FaultHandle:
        """Simulate fault injection.

        Args:
            scenario: Type of fault to inject.
            affected_components: Components to target (defaults based on scenario).

        Returns:
            FaultHandle for tracking the injected fault.
        """
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        components = affected_components or self.SCENARIO_COMPONENTS.get(
            scenario, ("deliberation_service",)
        )
        handle = FaultHandle(
            handle_id=uuid4(),
            scenario=scenario,
            started_at_ms=now_ms,
            affected_components=components,
        )

        self._active_faults[handle.handle_id] = handle
        self._inject_calls.append(
            {
                "scenario": scenario,
                "affected_components": components,
                "handle_id": handle.handle_id,
                "timestamp": datetime.now(timezone.utc),
            }
        )

        return handle

    async def remove_fault(
        self,
        handle: FaultHandle,
    ) -> bool:
        """Simulate fault removal.

        Args:
            handle: Handle of fault to remove.

        Returns:
            True if fault was removed, False if not found.
        """
        self._remove_calls.append(
            {
                "handle_id": handle.handle_id,
                "timestamp": datetime.now(timezone.utc),
            }
        )

        if handle.handle_id in self._active_faults:
            del self._active_faults[handle.handle_id]
            return True
        return False

    def get_active_faults(self) -> list[FaultHandle]:
        """Get currently active faults.

        Returns:
            List of active FaultHandle objects.
        """
        return list(self._active_faults.values())

    async def clear_all_faults(self) -> None:
        """Remove all active faults."""
        self._active_faults.clear()

    def _generate_recovery_time(self) -> float:
        """Generate a simulated recovery time.

        Returns:
            Recovery time in milliseconds.
        """
        if self._forced_recovery_ms:
            return self._forced_recovery_ms
        base = self._base_recovery_ms
        variance = random.uniform(
            -self._recovery_variance_ms, self._recovery_variance_ms
        )
        return max(1.0, base + variance)

    def _generate_audit_entries(
        self,
        scenario: ChaosScenario,
        injection_started: datetime,
        injection_ended: datetime,
        recovery_detected: datetime,
    ) -> list[dict[str, Any]]:
        """Generate simulated audit log entries.

        Args:
            scenario: The scenario being executed.
            injection_started: When fault injection began.
            injection_ended: When fault injection ended.
            recovery_detected: When recovery was detected.

        Returns:
            List of audit log entry dictionaries.
        """
        return [
            {
                "timestamp": injection_started.isoformat(),
                "event": "fault_injection_start",
                "scenario": scenario.value,
                "level": "WARNING",
                "message": f"Starting {scenario.value} chaos injection",
            },
            {
                "timestamp": injection_ended.isoformat(),
                "event": "fault_injection_end",
                "scenario": scenario.value,
                "level": "INFO",
                "message": f"Ended {scenario.value} chaos injection",
            },
            {
                "timestamp": recovery_detected.isoformat(),
                "event": "recovery_detected",
                "scenario": scenario.value,
                "level": "INFO",
                "message": f"System recovered from {scenario.value}",
            },
        ]

    # Test helpers for deterministic testing

    def set_forced_outcome(self, outcome: ChaosTestOutcome) -> None:
        """Force a specific outcome for deterministic testing.

        Args:
            outcome: The outcome to force for all subsequent tests.
        """
        self._forced_outcome = outcome

    def set_forced_recovery_ms(self, recovery_ms: float) -> None:
        """Force a specific recovery time for deterministic testing.

        Args:
            recovery_ms: Recovery time in milliseconds.
        """
        self._forced_recovery_ms = recovery_ms

    def set_forced_deliberations_affected(self, count: int) -> None:
        """Force a specific deliberations affected count.

        Args:
            count: Number of deliberations to report as affected.
        """
        self._forced_deliberations_affected = count

    def set_forced_witness_chain_intact(self, intact: bool) -> None:
        """Force a specific witness chain integrity status.

        Args:
            intact: Whether witness chain should be reported as intact.
        """
        self._forced_witness_chain_intact = intact

    def get_test_count(self) -> int:
        """Get number of chaos tests run.

        Returns:
            Count of tests executed.
        """
        return len(self._test_history)

    def get_test_history(self) -> list[dict[str, Any]]:
        """Get full test history.

        Returns:
            List of test run records.
        """
        return list(self._test_history)

    def get_inject_call_count(self) -> int:
        """Get number of inject_fault calls.

        Returns:
            Count of fault injection calls.
        """
        return len(self._inject_calls)

    def get_inject_calls(self) -> list[dict[str, Any]]:
        """Get full inject call history.

        Returns:
            List of inject_fault call records.
        """
        return list(self._inject_calls)

    def get_remove_call_count(self) -> int:
        """Get number of remove_fault calls.

        Returns:
            Count of fault removal calls.
        """
        return len(self._remove_calls)

    def get_remove_calls(self) -> list[dict[str, Any]]:
        """Get full remove call history.

        Returns:
            List of remove_fault call records.
        """
        return list(self._remove_calls)

    def clear(self) -> None:
        """Clear all state for test isolation."""
        self._active_faults.clear()
        self._test_history.clear()
        self._inject_calls.clear()
        self._remove_calls.clear()
        self._forced_outcome = None
        self._forced_recovery_ms = None
        self._forced_deliberations_affected = None
        self._forced_witness_chain_intact = None
