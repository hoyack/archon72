# Story 2B.8: Deliberation Chaos Testing

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2b-8 |
| **Epic** | Epic 2B: Deliberation Edge Cases & Guarantees |
| **Priority** | P0 |
| **Status** | done |
| **Created** | 2026-01-19 |

## User Story

**As a** quality engineer,
**I want** chaos tests for deliberation failure scenarios,
**So that** we verify graceful handling of faults.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.9 | System SHALL enforce deliberation timeout (5 minutes default) with auto-ESCALATE on expiry | P0 |
| FR-11.10 | System SHALL auto-ESCALATE after 3 deliberation rounds without supermajority (deadlock) | P0 |
| FR-11.12 | System SHALL preserve complete deliberation transcript for audit reconstruction | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target | Measurement |
|--------|-------------|--------|-------------|
| NFR-9.3 | FMEA scenario coverage | All 10 critical failure modes | Chaos test pass rate |
| NFR-9.5 | Chaos testing | Scheduler crash recovery | Test suite execution |
| NFR-3.6 | System availability | 99.9% uptime | Recovery time |
| NFR-10.6 | Archon substitution latency | < 10 seconds on failure | Substitution timing |

### Constitutional Truths

- **CT-11**: "Silent failure destroys legitimacy" - All failures MUST be reported
- **CT-12**: "Every action that affects an Archon must be witnessed" - Witness chain integrity during chaos
- **CT-14**: "Every claim terminates in visible, witnessed fate" - No lost petitions during failures

## Acceptance Criteria

### AC-1: Chaos Test Configuration Model

**Given** the need for configurable chaos testing
**When** I define the configuration model
**Then** `ChaosTestConfig` captures:
- `scenario_type`: Type of chaos to inject (ARCHON_TIMEOUT, SERVICE_RESTART, DB_FAILURE, API_DEGRADATION)
- `injection_duration_seconds`: How long to inject the fault (default: 30)
- `injection_probability`: Probability of fault occurring (0.0-1.0, default: 1.0)
- `affected_components`: List of components to target
- `recovery_timeout_seconds`: How long to wait for recovery (default: 60)
- `enable_audit_logging`: Whether to capture detailed chaos logs (default: true)
**And** the config validates all invariants (positive durations, valid probabilities)

### AC-2: Chaos Test Scenario Enumeration

**Given** the defined failure scenarios
**When** I enumerate scenario types
**Then** the following scenarios exist:
- `ARCHON_TIMEOUT_MID_PHASE`: One Archon stops responding during deliberation
- `SERVICE_RESTART`: Deliberation service killed and restarted
- `DATABASE_CONNECTION_FAILURE`: Database connection severed for configured duration
- `CREWAI_API_DEGRADATION`: Latency injected into CrewAI calls
- `WITNESS_WRITE_FAILURE`: Event writer becomes unavailable
- `NETWORK_PARTITION`: Network partition between components
**And** each scenario has expected recovery behavior documented

### AC-3: Archon Timeout Mid-Phase Scenario

**Given** a deliberation in progress
**When** one Archon stops responding mid-phase
**Then** the archon substitution mechanism activates (per Story 2B-4)
**And** substitution completes within 10 seconds (NFR-10.6)
**And** the deliberation continues with the replacement Archon
**And** the timeout and substitution are witnessed events
**And** the deliberation completes successfully

### AC-4: Deliberation Service Restart Scenario

**Given** a deliberation in progress with phase witnesses
**When** the deliberation service container is killed
**Then** in-flight deliberations resume from last witness checkpoint
**And** no deliberation data is lost
**And** the service recovers within configured timeout
**And** all previously witnessed phases are not re-executed
**And** audit logs capture the recovery timeline

### AC-5: Database Connection Failure Scenario

**Given** a deliberation in progress
**When** database connection is severed for 30 seconds
**Then** retry policy engages with exponential backoff
**And** no data loss occurs during reconnection
**And** deliberation either completes after reconnection or times out gracefully
**And** all in-flight transactions are either committed or rolled back atomically
**And** audit logs capture connection failure and recovery

### AC-6: CrewAI API Degradation Scenario

**Given** a deliberation in progress
**When** 500ms latency is injected into CrewAI calls
**Then** individual Archon timeouts may trigger substitution
**And** full deliberation does not fail due to slow responses
**And** the system adapts to degraded performance
**And** latency metrics are captured for analysis

### AC-7: Witness Write Failure Scenario

**Given** a deliberation attempting to write witness events
**When** the event writer becomes unavailable
**Then** the deliberation pauses (no silent continuation)
**And** retry policy engages for event writing
**And** deliberation either resumes after recovery or times out
**And** no unwitnessed phase completions occur (CT-12)

### AC-8: Chaos Test Report Model

**Given** a completed chaos test execution
**When** I receive results
**Then** `ChaosTestReport` contains:
- `test_id`: UUID identifying this test run
- `scenario`: The scenario that was executed
- `config`: The ChaosTestConfig used
- `started_at`: Test start timestamp (UTC)
- `completed_at`: Test completion timestamp (UTC)
- `injection_started_at`: When fault injection began
- `injection_ended_at`: When fault injection ended
- `recovery_detected_at`: When system recovery was detected
- `recovery_duration_ms`: Time from injection end to recovery
- `outcome`: SUCCESS, FAILURE, PARTIAL_RECOVERY
- `deliberations_affected`: Count of deliberations impacted
- `deliberations_recovered`: Count that successfully recovered
- `deliberations_failed`: Count that failed due to chaos
- `witness_chain_intact`: Boolean indicating witness integrity
- `audit_log_entries`: List of audit events during test
- `failure_details`: If failed, details of what went wrong
**And** the report can generate a summary string
**And** the report can export to JSON/dict

### AC-9: Chaos Test Harness Protocol

**Given** the need for chaos test infrastructure
**When** I define the protocol
**Then** `ChaosTestHarnessProtocol` has methods:
- `run_chaos_test(config: ChaosTestConfig) -> ChaosTestReport`
- `inject_fault(scenario: ChaosScenario) -> FaultHandle`
- `remove_fault(handle: FaultHandle) -> bool`
- `get_active_faults() -> list[FaultHandle]`
- `clear_all_faults() -> None`
**And** the protocol supports both sync and async fault injection
**And** all methods return fully-typed domain models

### AC-10: Audit-Friendly Logging

**Given** any chaos scenario execution
**When** the test runs
**Then** all chaos events produce structured logs:
- Fault injection start (timestamp, scenario, affected components)
- Fault active (heartbeat every 5 seconds)
- Fault removal (timestamp, duration)
- Recovery detection (timestamp, recovery metrics)
- Test completion (outcome, summary)
**And** logs are queryable by test_id
**And** logs follow structlog format

### AC-11: Stub Implementation for Testing

**Given** the need for fast unit tests
**When** tests run
**Then** `ChaosTestHarnessStub` provides in-memory implementation
**And** the stub implements full `ChaosTestHarnessProtocol`
**And** the stub supports configurable fault injection simulation
**And** the stub tracks call history for verification
**And** the stub can simulate all scenario outcomes

### AC-12: Unit Tests

**Given** the ChaosTestHarness and related models
**Then** unit tests verify:
- ChaosTestConfig creation with valid defaults
- ChaosTestConfig validation rejects invalid values
- ChaosTestScenario enumeration completeness
- ChaosTestReport creation and summary generation
- Stub tracks fault injection/removal calls
- All scenarios can be instantiated

### AC-13: Integration Tests

**Given** the chaos test harness
**Then** integration tests verify:
- Archon timeout triggers substitution (AC-3)
- Service restart recovers from checkpoint (AC-4)
- Database failure engages retry policy (AC-5)
- API degradation does not cause full failure (AC-6)
- Witness failure pauses deliberation (AC-7)
- All chaos scenarios produce audit logs
- No silent failures occur (CT-11)
- All affected petitions reach terminal fate (CT-14)

## Technical Design

### Domain Models

```python
# src/domain/models/chaos_test_config.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChaosScenario(Enum):
    """Enumeration of chaos test scenarios (Story 2B.8, NFR-9.5).

    Each scenario represents a specific failure mode to inject
    during deliberation testing.
    """

    ARCHON_TIMEOUT_MID_PHASE = "archon_timeout_mid_phase"
    SERVICE_RESTART = "service_restart"
    DATABASE_CONNECTION_FAILURE = "database_connection_failure"
    CREWAI_API_DEGRADATION = "crewai_api_degradation"
    WITNESS_WRITE_FAILURE = "witness_write_failure"
    NETWORK_PARTITION = "network_partition"


@dataclass(frozen=True, eq=True)
class ChaosTestConfig:
    """Configuration for chaos testing deliberation systems (Story 2B.8, NFR-9.5).

    Defines the parameters for chaos test execution including scenario type,
    injection duration, and recovery expectations.

    Attributes:
        scenario: Type of chaos to inject.
        injection_duration_seconds: How long to inject the fault (default: 30).
        injection_probability: Probability of fault occurring (default: 1.0).
        affected_components: List of components to target.
        recovery_timeout_seconds: How long to wait for recovery (default: 60).
        enable_audit_logging: Whether to capture detailed chaos logs (default: True).
        latency_injection_ms: For API_DEGRADATION, the latency to inject (default: 500).
    """

    scenario: ChaosScenario
    injection_duration_seconds: int = field(default=30)
    injection_probability: float = field(default=1.0)
    affected_components: tuple[str, ...] = field(default_factory=tuple)
    recovery_timeout_seconds: int = field(default=60)
    enable_audit_logging: bool = field(default=True)
    latency_injection_ms: int = field(default=500)

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if self.injection_duration_seconds < 1:
            raise ValueError(
                f"injection_duration_seconds must be >= 1, got {self.injection_duration_seconds}"
            )
        if self.injection_duration_seconds > 300:
            raise ValueError(
                f"injection_duration_seconds must be <= 300, got {self.injection_duration_seconds}"
            )
        if not 0.0 <= self.injection_probability <= 1.0:
            raise ValueError(
                f"injection_probability must be 0.0-1.0, got {self.injection_probability}"
            )
        if self.recovery_timeout_seconds < 1:
            raise ValueError(
                f"recovery_timeout_seconds must be >= 1, got {self.recovery_timeout_seconds}"
            )
        if self.latency_injection_ms < 0:
            raise ValueError(
                f"latency_injection_ms must be >= 0, got {self.latency_injection_ms}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "scenario": self.scenario.value,
            "injection_duration_seconds": self.injection_duration_seconds,
            "injection_probability": self.injection_probability,
            "affected_components": list(self.affected_components),
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "enable_audit_logging": self.enable_audit_logging,
            "latency_injection_ms": self.latency_injection_ms,
            "schema_version": 1,
        }
```

```python
# src/domain/models/chaos_test_report.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class ChaosTestOutcome(Enum):
    """Outcome of a chaos test execution."""

    SUCCESS = "success"  # System recovered fully
    FAILURE = "failure"  # System did not recover
    PARTIAL_RECOVERY = "partial_recovery"  # Some but not all recovered


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
        recovery_detected_at: When system recovery was detected.
        outcome: SUCCESS, FAILURE, or PARTIAL_RECOVERY.
        deliberations_affected: Count of deliberations impacted.
        deliberations_recovered: Count that successfully recovered.
        deliberations_failed: Count that failed due to chaos.
        witness_chain_intact: Boolean indicating witness integrity.
        audit_log_entries: List of audit events during test.
        failure_details: If failed, details of what went wrong.
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
        """Get recovery duration in milliseconds."""
        if self.recovery_detected_at is None:
            return None
        return (self.recovery_detected_at - self.injection_ended_at).total_seconds() * 1000

    @property
    def injection_duration_ms(self) -> float:
        """Get fault injection duration in milliseconds."""
        return (self.injection_ended_at - self.injection_started_at).total_seconds() * 1000

    @property
    def total_duration_seconds(self) -> float:
        """Get total test duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def recovery_rate(self) -> float:
        """Get recovery rate as percentage."""
        if self.deliberations_affected == 0:
            return 100.0
        return (self.deliberations_recovered / self.deliberations_affected) * 100

    def summary(self) -> str:
        """Generate human-readable summary."""
        recovery_str = f"{self.recovery_duration_ms:.0f}ms" if self.recovery_duration_ms else "N/A"
        witness_str = "INTACT" if self.witness_chain_intact else "BROKEN"
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
            f"Audit Log Entries: {len(self.audit_log_entries)}\n"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "test_id": str(self.test_id),
            "scenario": self.scenario,
            "config": self.config,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "injection_started_at": self.injection_started_at.isoformat(),
            "injection_ended_at": self.injection_ended_at.isoformat(),
            "recovery_detected_at": self.recovery_detected_at.isoformat() if self.recovery_detected_at else None,
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
            "schema_version": 1,
        }
```

### Protocol Definition

```python
# src/application/ports/chaos_test_harness.py

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
    """

    handle_id: UUID
    scenario: ChaosScenario
    started_at_ms: int
    affected_components: tuple[str, ...]


class ChaosTestHarnessProtocol(Protocol):
    """Protocol for chaos testing deliberation systems (Story 2B.8, NFR-9.5).

    Implementations coordinate fault injection and recovery testing
    for validating system resilience under failure conditions.

    Constitutional Constraints:
    - CT-11: Report all failures (no silent drops)
    - CT-12: Verify witness chain integrity during chaos
    - CT-14: Every petition terminates in witnessed fate
    """

    async def run_chaos_test(
        self,
        config: ChaosTestConfig,
    ) -> ChaosTestReport:
        """Execute a chaos test with the given configuration.

        Injects faults, monitors system behavior, and generates
        a comprehensive report on recovery.

        Args:
            config: Chaos test configuration parameters.

        Returns:
            ChaosTestReport with complete metrics and analysis.
        """
        ...

    async def inject_fault(
        self,
        scenario: ChaosScenario,
        affected_components: tuple[str, ...] | None = None,
    ) -> FaultHandle:
        """Inject a specific fault into the system.

        Starts fault injection that will persist until removed.

        Args:
            scenario: The type of fault to inject.
            affected_components: Optional specific components to target.

        Returns:
            FaultHandle for tracking and removal.
        """
        ...

    async def remove_fault(
        self,
        handle: FaultHandle,
    ) -> bool:
        """Remove a previously injected fault.

        Stops the fault injection and allows recovery.

        Args:
            handle: The fault handle from inject_fault.

        Returns:
            True if fault was removed, False if not found.
        """
        ...

    def get_active_faults(self) -> list[FaultHandle]:
        """Get list of currently active fault injections.

        Returns:
            List of active FaultHandle objects.
        """
        ...

    async def clear_all_faults(self) -> None:
        """Remove all active fault injections.

        Emergency cleanup method for test teardown.
        """
        ...
```

### Stub Implementation

```python
# src/infrastructure/stubs/chaos_test_harness_stub.py

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from src.domain.models.chaos_test_config import ChaosScenario, ChaosTestConfig
from src.domain.models.chaos_test_report import ChaosTestOutcome, ChaosTestReport


class FaultHandle:
    """Handle for an active fault injection."""

    def __init__(
        self,
        handle_id: UUID,
        scenario: ChaosScenario,
        started_at_ms: int,
        affected_components: tuple[str, ...],
    ) -> None:
        self.handle_id = handle_id
        self.scenario = scenario
        self.started_at_ms = started_at_ms
        self.affected_components = affected_components


class ChaosTestHarnessStub:
    """Stub implementation of ChaosTestHarnessProtocol for testing.

    Simulates chaos test execution with configurable behavior
    for fast unit and integration tests.

    Attributes:
        _active_faults: Currently active fault injections.
        _test_history: History of chaos test runs.
        _inject_calls: History of inject_fault calls.
        _remove_calls: History of remove_fault calls.
    """

    SCENARIO_OUTCOMES: dict[ChaosScenario, ChaosTestOutcome] = {
        ChaosScenario.ARCHON_TIMEOUT_MID_PHASE: ChaosTestOutcome.SUCCESS,
        ChaosScenario.SERVICE_RESTART: ChaosTestOutcome.SUCCESS,
        ChaosScenario.DATABASE_CONNECTION_FAILURE: ChaosTestOutcome.SUCCESS,
        ChaosScenario.CREWAI_API_DEGRADATION: ChaosTestOutcome.SUCCESS,
        ChaosScenario.WITNESS_WRITE_FAILURE: ChaosTestOutcome.PARTIAL_RECOVERY,
        ChaosScenario.NETWORK_PARTITION: ChaosTestOutcome.SUCCESS,
    }

    def __init__(
        self,
        base_recovery_ms: float = 100.0,
        recovery_variance_ms: float = 50.0,
    ) -> None:
        """Initialize stub with configurable recovery timing."""
        self._active_faults: dict[UUID, FaultHandle] = {}
        self._test_history: list[dict[str, Any]] = []
        self._inject_calls: list[dict[str, Any]] = []
        self._remove_calls: list[dict[str, Any]] = []
        self._base_recovery_ms = base_recovery_ms
        self._recovery_variance_ms = recovery_variance_ms
        self._forced_outcome: ChaosTestOutcome | None = None
        self._forced_recovery_ms: float | None = None

    async def run_chaos_test(
        self,
        config: ChaosTestConfig,
    ) -> ChaosTestReport:
        """Simulate chaos test execution."""
        started_at = datetime.now(timezone.utc)

        # Record test run
        self._test_history.append({
            "config": config,
            "timestamp": started_at,
        })

        # Simulate fault injection
        injection_started_at = started_at

        # Simulate injection duration (scaled down for testing)
        await asyncio.sleep(0.01)  # Minimal delay for test

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
        deliberations_affected = random.randint(5, 20)
        if outcome == ChaosTestOutcome.SUCCESS:
            deliberations_recovered = deliberations_affected
            deliberations_failed = 0
        elif outcome == ChaosTestOutcome.PARTIAL_RECOVERY:
            deliberations_recovered = int(deliberations_affected * 0.8)
            deliberations_failed = deliberations_affected - deliberations_recovered
        else:
            deliberations_recovered = 0
            deliberations_failed = deliberations_affected

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
            witness_chain_intact=(outcome != ChaosTestOutcome.FAILURE),
            audit_log_entries=tuple(audit_entries),
            failure_details=None if outcome == ChaosTestOutcome.SUCCESS else "Simulated failure",
        )

    async def inject_fault(
        self,
        scenario: ChaosScenario,
        affected_components: tuple[str, ...] | None = None,
    ) -> FaultHandle:
        """Simulate fault injection."""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        handle = FaultHandle(
            handle_id=uuid4(),
            scenario=scenario,
            started_at_ms=now_ms,
            affected_components=affected_components or ("deliberation_service",),
        )

        self._active_faults[handle.handle_id] = handle
        self._inject_calls.append({
            "scenario": scenario,
            "affected_components": affected_components,
            "handle_id": handle.handle_id,
            "timestamp": datetime.now(timezone.utc),
        })

        return handle

    async def remove_fault(
        self,
        handle: FaultHandle,
    ) -> bool:
        """Simulate fault removal."""
        self._remove_calls.append({
            "handle_id": handle.handle_id,
            "timestamp": datetime.now(timezone.utc),
        })

        if handle.handle_id in self._active_faults:
            del self._active_faults[handle.handle_id]
            return True
        return False

    def get_active_faults(self) -> list[FaultHandle]:
        """Get currently active faults."""
        return list(self._active_faults.values())

    async def clear_all_faults(self) -> None:
        """Remove all active faults."""
        self._active_faults.clear()

    def _generate_recovery_time(self) -> float:
        """Generate a simulated recovery time."""
        if self._forced_recovery_ms:
            return self._forced_recovery_ms
        base = self._base_recovery_ms
        variance = random.uniform(-self._recovery_variance_ms, self._recovery_variance_ms)
        return max(1.0, base + variance)

    def _generate_audit_entries(
        self,
        scenario: ChaosScenario,
        injection_started: datetime,
        injection_ended: datetime,
        recovery_detected: datetime,
    ) -> list[dict[str, Any]]:
        """Generate simulated audit log entries."""
        return [
            {
                "timestamp": injection_started.isoformat(),
                "event": "fault_injection_start",
                "scenario": scenario.value,
                "level": "WARNING",
            },
            {
                "timestamp": injection_ended.isoformat(),
                "event": "fault_injection_end",
                "scenario": scenario.value,
                "level": "INFO",
            },
            {
                "timestamp": recovery_detected.isoformat(),
                "event": "recovery_detected",
                "scenario": scenario.value,
                "level": "INFO",
            },
        ]

    # Test helpers

    def set_forced_outcome(self, outcome: ChaosTestOutcome) -> None:
        """Force a specific outcome for deterministic testing."""
        self._forced_outcome = outcome

    def set_forced_recovery_ms(self, recovery_ms: float) -> None:
        """Force a specific recovery time for deterministic testing."""
        self._forced_recovery_ms = recovery_ms

    def get_test_count(self) -> int:
        """Get number of chaos tests run."""
        return len(self._test_history)

    def get_inject_call_count(self) -> int:
        """Get number of inject_fault calls."""
        return len(self._inject_calls)

    def get_remove_call_count(self) -> int:
        """Get number of remove_fault calls."""
        return len(self._remove_calls)

    def clear(self) -> None:
        """Clear all state."""
        self._active_faults.clear()
        self._test_history.clear()
        self._inject_calls.clear()
        self._remove_calls.clear()
        self._forced_outcome = None
        self._forced_recovery_ms = None
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-4 | Deliberation Protocol Orchestrator | DONE | Core orchestration to test under chaos |
| petition-2b-2 | Deliberation Timeout Enforcement | DONE | Timeout behavior during chaos |
| petition-2b-4 | Archon Substitution on Failure | DONE | Substitution during Archon timeout chaos |
| petition-2b-5 | Transcript Preservation | DONE | Witness checkpoint recovery |
| petition-2b-7 | Load Testing Harness | DONE | Load harness infrastructure for chaos |

### Downstream Dependencies (Blocked By This Story)

None - this is the final story in Epic 2B.

## Implementation Tasks

### Task 1: Create Domain Models (AC: 1, 2, 8)
- [ ] Create `src/domain/models/chaos_test_config.py`
- [ ] Create `src/domain/models/chaos_test_report.py`
- [ ] Add ChaosScenario enumeration
- [ ] Add ChaosTestOutcome enumeration
- [ ] Add validation for all invariants
- [ ] Add `to_dict()` methods for serialization
- [ ] Export from `src/domain/models/__init__.py`

### Task 2: Create ChaosTestHarnessProtocol (AC: 9)
- [ ] Create `src/application/ports/chaos_test_harness.py`
- [ ] Define `ChaosTestHarnessProtocol` with all methods
- [ ] Define `FaultHandle` dataclass
- [ ] Add comprehensive docstrings with NFR references
- [ ] Export from `src/application/ports/__init__.py`

### Task 3: Create ChaosTestHarnessStub (AC: 11)
- [ ] Create `src/infrastructure/stubs/chaos_test_harness_stub.py`
- [ ] Implement all protocol methods with simulation
- [ ] Add configurable recovery timing
- [ ] Add outcome simulation per scenario
- [ ] Add test helpers (set_forced_outcome, clear)
- [ ] Export from `src/infrastructure/stubs/__init__.py`

### Task 4: Write Unit Tests (AC: 12)
- [ ] Create `tests/unit/domain/models/test_chaos_test_config.py`
- [ ] Create `tests/unit/domain/models/test_chaos_test_report.py`
- [ ] Create `tests/unit/infrastructure/stubs/test_chaos_test_harness_stub.py`
- [ ] Test config validation
- [ ] Test report summary generation
- [ ] Test scenario enumeration
- [ ] Test stub behavior and call tracking

### Task 5: Write Integration Tests (AC: 13)
- [ ] Create `tests/integration/test_chaos_testing_integration.py`
- [ ] Test Archon timeout scenario (AC-3)
- [ ] Test service restart scenario (AC-4)
- [ ] Test database failure scenario (AC-5)
- [ ] Test API degradation scenario (AC-6)
- [ ] Test witness failure scenario (AC-7)
- [ ] Verify audit logging for all scenarios (AC-10)
- [ ] Verify no silent failures (CT-11)

### Task 6: Update Module Exports
- [ ] Update `src/domain/models/__init__.py`
- [ ] Update `src/application/ports/__init__.py`
- [ ] Update `src/infrastructure/stubs/__init__.py`

## Definition of Done

- [ ] `ChaosTestConfig` domain model with validation
- [ ] `ChaosTestReport` domain model with summary generation
- [ ] `ChaosScenario` enumeration with all 6 scenarios
- [ ] `ChaosTestHarnessProtocol` defined with full interface
- [ ] `ChaosTestHarnessStub` provides test implementation
- [ ] Unit tests created (coverage for new code)
- [ ] Integration tests verify all chaos scenarios
- [ ] All chaos scenarios produce audit logs (AC-10)
- [ ] No silent failures during chaos (CT-11)
- [ ] Witness chain integrity verified (CT-12)

## Test Scenarios

### Scenario 1: Archon Timeout Mid-Phase

```python
# Setup
harness = ChaosTestHarnessStub()
config = ChaosTestConfig(
    scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
    injection_duration_seconds=10,
)

# Run
report = await harness.run_chaos_test(config)

assert report.outcome == ChaosTestOutcome.SUCCESS
assert report.deliberations_recovered == report.deliberations_affected
assert report.witness_chain_intact is True
assert len(report.audit_log_entries) >= 3
```

### Scenario 2: Service Restart Recovery

```python
# Setup
config = ChaosTestConfig(
    scenario=ChaosScenario.SERVICE_RESTART,
    injection_duration_seconds=30,
    recovery_timeout_seconds=60,
)

# Run
report = await harness.run_chaos_test(config)

assert report.outcome == ChaosTestOutcome.SUCCESS
assert report.recovery_duration_ms is not None
assert report.recovery_duration_ms < 60_000  # Under timeout
```

### Scenario 3: Database Connection Failure

```python
# Setup
config = ChaosTestConfig(
    scenario=ChaosScenario.DATABASE_CONNECTION_FAILURE,
    injection_duration_seconds=30,
)

# Run
report = await harness.run_chaos_test(config)

assert report.outcome == ChaosTestOutcome.SUCCESS
assert report.deliberations_failed == 0
```

### Scenario 4: Fault Injection Lifecycle

```python
# Setup
harness = ChaosTestHarnessStub()

# Inject fault
handle = await harness.inject_fault(
    scenario=ChaosScenario.CREWAI_API_DEGRADATION,
    affected_components=("crewai_adapter",),
)

# Verify active
assert len(harness.get_active_faults()) == 1

# Remove fault
removed = await harness.remove_fault(handle)
assert removed is True
assert len(harness.get_active_faults()) == 0
```

## Dev Notes

### Relevant Architecture Patterns

1. **Fault Injection Framework**:
   - Use dependency injection to swap real implementations with chaos stubs
   - Faults are reversible via FaultHandle
   - All faults have configurable duration and probability

2. **Recovery Detection**:
   - Monitor for successful operation completion after fault removal
   - Use heartbeat/liveness checks for component recovery
   - Capture recovery timing for SLA verification

3. **Audit Trail**:
   - Use structlog for consistent log format
   - Tag all chaos events with test_id for correlation
   - Preserve audit entries in report for post-mortem

### Key Files to Reference

| File | Why |
|------|-----|
| `src/application/services/archon_substitution_service.py` | Substitution during timeout chaos |
| `src/infrastructure/stubs/load_test_harness_stub.py` | Similar stub pattern |
| `src/domain/models/load_test_config.py` | Config model pattern |
| `tests/integration/test_archon_substitution_integration.py` | Integration test patterns |

### Integration Points

1. **DeliberationOrchestratorService**:
   - Chaos tests exercise orchestrator under failure conditions
   - Verify orchestrator resumes from checkpoint

2. **ArchonSubstitutionService**:
   - Archon timeout chaos validates substitution SLA
   - Verify substitution completes < 10 seconds

3. **PhaseWitnessBatchingService**:
   - Service restart chaos validates checkpoint recovery
   - Verify no unwitnessed phase completions

### CI Integration

1. **Manual Trigger**:
   - Chaos tests should not run on every PR
   - Add CI workflow with `workflow_dispatch` trigger
   - Label tests with `@pytest.mark.chaos`

2. **Test Environment**:
   - Chaos tests require isolated environment
   - Use test fixtures, not production data
   - Clean up all faults in teardown

## References

- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#NFR-9.3`] - FMEA scenario coverage
- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#NFR-9.5`] - Chaos testing requirement
- [Source: `_bmad-output/planning-artifacts/petition-system-epics.md#Story-2B.8`] - Story definition
- [Source: `_bmad-output/planning-artifacts/architecture.md#Chaos-Testing-Mandate`] - Chaos testing architecture
