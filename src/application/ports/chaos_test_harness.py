"""Chaos test harness protocol for deliberation resilience testing.

Story 2B.8: Deliberation Chaos Testing (NFR-9.5)

This module defines the protocol for chaos testing infrastructure that
validates system resilience under various failure conditions.

Constitutional Constraints:
- CT-11: Report all failures (no silent drops)
- CT-12: Verify witness chain integrity during chaos
- CT-14: Every petition terminates in witnessed fate
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from src.domain.models.chaos_test_config import ChaosScenario, ChaosTestConfig
from src.domain.models.chaos_test_report import ChaosTestReport


@dataclass(frozen=True)
class FaultHandle:
    """Handle for an active fault injection.

    Used to track and remove specific fault injections.
    FaultHandle instances are returned by inject_fault() and can be
    passed to remove_fault() to stop the injection.

    Attributes:
        handle_id: Unique identifier for this fault injection.
        scenario: Type of chaos scenario being injected.
        started_at_ms: Unix timestamp in milliseconds when injection started.
        affected_components: Components being affected by the fault.
    """

    handle_id: UUID
    scenario: ChaosScenario
    started_at_ms: int
    affected_components: tuple[str, ...]


class ChaosTestHarnessProtocol(Protocol):
    """Protocol for chaos testing deliberation systems (Story 2B.8, NFR-9.5).

    Implementations coordinate fault injection and recovery testing
    for validating system resilience under failure conditions.

    Chaos testing validates that the deliberation system maintains
    constitutional guarantees even under adverse conditions:

    - CT-11: All failures must be reported (no silent drops)
    - CT-12: Witness chain integrity must be preserved
    - CT-14: All petitions must reach terminal fate

    Supported chaos scenarios:
    - ARCHON_TIMEOUT_MID_PHASE: Archon becomes unresponsive
    - SERVICE_RESTART: Deliberation service killed and restarted
    - DATABASE_CONNECTION_FAILURE: Database becomes unavailable
    - CREWAI_API_DEGRADATION: Latency injected into AI calls
    - WITNESS_WRITE_FAILURE: Event writer becomes unavailable
    - NETWORK_PARTITION: Network partition between components

    Example:
        >>> harness = ChaosTestHarnessStub()
        >>> config = ChaosTestConfig(
        ...     scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
        ...     injection_duration_seconds=10,
        ... )
        >>> report = await harness.run_chaos_test(config)
        >>> assert report.outcome == ChaosTestOutcome.SUCCESS
    """

    async def run_chaos_test(
        self,
        config: ChaosTestConfig,
    ) -> ChaosTestReport:
        """Execute a chaos test with the given configuration.

        Injects faults according to the configuration, monitors system
        behavior, waits for recovery, and generates a comprehensive report.

        This method orchestrates the full chaos test lifecycle:
        1. Prepare test environment and baseline metrics
        2. Inject fault according to scenario
        3. Monitor system behavior during fault
        4. Remove fault after injection_duration
        5. Wait for recovery up to recovery_timeout
        6. Collect metrics and generate report

        Args:
            config: Chaos test configuration parameters including:
                - scenario: Type of fault to inject
                - injection_duration_seconds: How long to maintain fault
                - recovery_timeout_seconds: Max time to wait for recovery
                - enable_audit_logging: Whether to capture detailed logs

        Returns:
            ChaosTestReport with complete metrics including:
            - Timing information (injection, recovery)
            - Deliberation impact counts
            - Witness chain integrity status
            - Audit log entries from test

        Raises:
            ValueError: If configuration is invalid.
            RuntimeError: If test environment is not ready.
        """
        ...

    async def inject_fault(
        self,
        scenario: ChaosScenario,
        affected_components: tuple[str, ...] | None = None,
    ) -> FaultHandle:
        """Inject a specific fault into the system.

        Starts fault injection that will persist until explicitly removed
        via remove_fault(). Multiple faults can be active simultaneously.

        Args:
            scenario: The type of fault to inject. Determines the failure
                mode that will be simulated.
            affected_components: Optional specific components to target.
                If None, defaults to scenario-appropriate components.

        Returns:
            FaultHandle for tracking and later removal of this fault.
            The handle contains the unique ID and start timestamp.

        Raises:
            ValueError: If scenario is invalid.
            RuntimeError: If fault injection fails to start.
        """
        ...

    async def remove_fault(
        self,
        handle: FaultHandle,
    ) -> bool:
        """Remove a previously injected fault.

        Stops the fault injection associated with the given handle,
        allowing the system to begin recovery.

        Args:
            handle: The fault handle returned from inject_fault().

        Returns:
            True if the fault was found and removed.
            False if no fault with that handle was active.
        """
        ...

    def get_active_faults(self) -> list[FaultHandle]:
        """Get list of currently active fault injections.

        Returns:
            List of FaultHandle objects for all active faults.
            Empty list if no faults are currently active.
        """
        ...

    async def clear_all_faults(self) -> None:
        """Remove all active fault injections.

        Emergency cleanup method that removes all active faults
        regardless of their handles. Use for test teardown or
        when normal fault removal has failed.

        This method is idempotent and will not raise errors
        even if there are no active faults.
        """
        ...
