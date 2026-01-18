"""TaskTimeoutPort - Interface for automatic task state transitions based on timeouts.

Story: consent-gov-2.5: Task TTL & Auto-Transitions

This port defines the contract for processing automatic task state transitions
when timeouts expire. The Golden Rule is: "Failure is allowed; silence is not."

Constitutional Guarantees:
- Every timeout MUST emit an explicit event (no silent expiry)
- Auto-transitions use "system" as actor (no Cluster blame)
- NO penalty attribution on any timeout
- All transitions are witnessed in the ledger

Timeout Scenarios:
1. Activation TTL (72h): ROUTED → DECLINED (ttl_expired)
2. Acceptance Inactivity (48h): ACCEPTED → IN_PROGRESS (auto_started)
3. Reporting Timeout (7d): IN_PROGRESS → QUARANTINED (reporting_timeout)

References:
- FR8: Auto-decline after TTL expiration with no failure attribution
- FR9: Auto-transition accepted → in_progress after inactivity
- FR10: Auto-quarantine tasks exceeding reporting timeout
- NFR-CONSENT-01: TTL expiration → declined state
- Golden Rule: Failure is allowed; silence is not
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class TaskTimeoutConfig:
    """Configuration for task timeout durations.

    All values are configurable, with sensible defaults per the PRD.
    These timeouts define when automatic state transitions occur.

    Attributes:
        activation_ttl: Time for Cluster to respond to routed task.
            After this, ROUTED → DECLINED (ttl_expired).
            Default: 72 hours per NFR-CONSENT-01.

        acceptance_inactivity: Time after acceptance before auto-start.
            After this, ACCEPTED → IN_PROGRESS (auto_started).
            Default: 48 hours per FR9.

        reporting_timeout: Time for in-progress task to report.
            After this, IN_PROGRESS → QUARANTINED (reporting_timeout).
            Default: 7 days per FR10.

        processor_interval: How often to check for timeouts.
            Default: 5 minutes.
    """

    activation_ttl: timedelta = field(default_factory=lambda: timedelta(hours=72))
    acceptance_inactivity: timedelta = field(
        default_factory=lambda: timedelta(hours=48)
    )
    reporting_timeout: timedelta = field(default_factory=lambda: timedelta(days=7))
    processor_interval: timedelta = field(default_factory=lambda: timedelta(minutes=5))

    def __post_init__(self) -> None:
        """Validate all timeout values are positive."""
        if self.activation_ttl <= timedelta(0):
            raise ValueError("activation_ttl must be positive")
        if self.acceptance_inactivity <= timedelta(0):
            raise ValueError("acceptance_inactivity must be positive")
        if self.reporting_timeout <= timedelta(0):
            raise ValueError("reporting_timeout must be positive")
        if self.processor_interval <= timedelta(0):
            raise ValueError("processor_interval must be positive")


@dataclass(frozen=True)
class TimeoutProcessingResult:
    """Result of processing all timeout scenarios.

    Each field contains the list of task IDs that were transitioned
    during this processing run.

    Attributes:
        declined: Tasks transitioned ROUTED → DECLINED (TTL expired).
        started: Tasks transitioned ACCEPTED → IN_PROGRESS (inactivity).
        quarantined: Tasks transitioned IN_PROGRESS → QUARANTINED (reporting).
        errors: List of (task_id, error_message) tuples for failed transitions.
    """

    declined: list[UUID] = field(default_factory=list)
    started: list[UUID] = field(default_factory=list)
    quarantined: list[UUID] = field(default_factory=list)
    errors: list[tuple[UUID, str]] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total number of tasks successfully transitioned."""
        return len(self.declined) + len(self.started) + len(self.quarantined)

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred during processing."""
        return len(self.errors) > 0


@runtime_checkable
class TaskTimeoutPort(Protocol):
    """Port for automatic task timeout processing.

    This interface defines the contract for detecting and processing
    task timeouts. Implementations must:

    1. Query tasks past their respective timeouts
    2. Transition to appropriate states
    3. Emit events with "system" as actor
    4. Record NO penalty attribution

    Constitutional Guarantee:
    - Every timeout produces an explicit event (no silent expiry)
    - Actor is always "system" (not the Cluster)
    - penalty_incurred is always false

    The Golden Rule: Failure is allowed; silence is not.
    This means every timeout MUST emit an event to the ledger.
    """

    async def process_all_timeouts(self) -> TimeoutProcessingResult:
        """Process all timeout scenarios in one batch.

        This is the main entry point for timeout processing.
        It processes:
        1. Activation TTL timeouts (ROUTED → DECLINED)
        2. Acceptance inactivity timeouts (ACCEPTED → IN_PROGRESS)
        3. Reporting timeouts (IN_PROGRESS → QUARANTINED)

        Constitutional Guarantee:
        - All transitions emit events with "system" as actor
        - NO penalty attribution on any transition
        - No silent expirations - every timeout is witnessed

        Returns:
            TimeoutProcessingResult with lists of transitioned task IDs.
        """
        ...

    async def process_activation_timeouts(self) -> list[UUID]:
        """Process tasks past activation TTL.

        Finds all tasks in ROUTED state past their TTL and transitions
        them to DECLINED with reason "ttl_expired".

        Per FR8: Auto-decline after TTL expiration with no failure attribution.
        Per NFR-CONSENT-01: TTL expiration → declined state.

        Constitutional Guarantee:
        - Emits "executive.task.auto_declined" event
        - Actor is "system" (not the Cluster)
        - Reason is "ttl_expired" (not "failure")
        - penalty_incurred is false

        Returns:
            List of task IDs that were auto-declined.
        """
        ...

    async def process_acceptance_timeouts(self) -> list[UUID]:
        """Process tasks inactive after acceptance.

        Finds all tasks in ACCEPTED state past their inactivity timeout
        and transitions them to IN_PROGRESS with reason "acceptance_inactivity".

        Per FR9: Auto-transition accepted → in_progress after inactivity.
        Rationale: Cluster accepted, assumed to be working.

        Constitutional Guarantee:
        - Emits "executive.task.auto_started" event
        - Actor is "system" (not the Cluster)
        - This is procedural, not punitive

        Returns:
            List of task IDs that were auto-started.
        """
        ...

    async def process_reporting_timeouts(self) -> list[UUID]:
        """Process tasks past reporting deadline.

        Finds all tasks in IN_PROGRESS state past their reporting timeout
        and transitions them to QUARANTINED with reason "reporting_timeout".

        Per FR10: Auto-quarantine tasks exceeding reporting timeout.
        Rationale: Silence isn't failure, it's unknown. Quarantine for investigation.

        Constitutional Guarantee:
        - Emits "executive.task.auto_quarantined" event
        - Actor is "system" (not the Cluster)
        - NO penalty attribution (silence isn't negligence)
        - penalty_incurred is false

        Returns:
            List of task IDs that were auto-quarantined.
        """
        ...

    def get_config(self) -> TaskTimeoutConfig:
        """Get the current timeout configuration.

        Returns:
            Current TaskTimeoutConfig with all timeout values.
        """
        ...


@runtime_checkable
class TimeoutSchedulerPort(Protocol):
    """Port for scheduling periodic timeout processing.

    This interface defines the contract for running timeout checks
    on a schedule. Implementations must run non-blocking.

    The scheduler should call TaskTimeoutPort.process_all_timeouts()
    at the configured interval (default: every 5 minutes).
    """

    async def start(self) -> None:
        """Start the periodic timeout processing.

        Begins running timeout checks at the configured interval.
        This should be non-blocking (run in background).
        """
        ...

    async def stop(self) -> None:
        """Stop the periodic timeout processing.

        Gracefully stops the scheduler, completing any in-progress
        processing before returning.
        """
        ...

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is currently running.

        Returns:
            True if scheduler is actively processing timeouts.
        """
        ...

    @property
    def last_run_result(self) -> TimeoutProcessingResult | None:
        """Get the result of the last processing run.

        Returns:
            TimeoutProcessingResult from last run, or None if never run.
        """
        ...
