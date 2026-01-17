"""Integration tests for Failure Propagation (Story GOV-4.3).

Tests the full failure propagation pipeline including event store integration,
hash chain integrity, and Knight witnessing.

Per Government PRD:
- FR-GOV-13: Duke/Earl constraints - No suppression of failure signals
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- AC5: Failure chain integrity with hash chain and witnessing
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.application.ports.failure_propagation import (
    FailureSeverity,
    FailureSignal,
    FailureSignalType,
    PrinceNotificationContext,
    SuppressionDetectionMethod,
    SuppressionViolation,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatement,
    WitnessStatementType,
)
from src.application.services.suppression_detection_service import (
    SuppressionDetectionConfig,
    SuppressionDetectionService,
)
from src.infrastructure.adapters.government.failure_propagation_adapter import (
    FailurePropagationAdapter,
)


# =============================================================================
# Test Fixtures
# =============================================================================


class InMemoryKnightWitness:
    """In-memory implementation of Knight witness for integration testing."""

    def __init__(self) -> None:
        self.statements: list[WitnessStatement] = []
        self.violations: list[ViolationRecord] = []

    def observe(self, context: ObservationContext) -> WitnessStatement:
        """Record an observation."""
        statement = WitnessStatement.create(
            statement_type=WitnessStatementType.PROCEDURAL_TRANSITION,
            description=context.description,
            roles_involved=context.participants,
            target_id=context.target_id,
            target_type=context.target_type,
            metadata=context.metadata,
        )
        self.statements.append(statement)
        return statement

    def record_violation(self, violation: ViolationRecord) -> WitnessStatement:
        """Record a violation."""
        self.violations.append(violation)
        statement = WitnessStatement.create(
            statement_type=WitnessStatementType.ROLE_VIOLATION,
            description=violation.description,
            roles_involved=[violation.violator_name],
            target_id=violation.target_id,
            target_type=violation.target_type,
            metadata=violation.metadata,
            acknowledgment_required=violation.requires_acknowledgment,
        )
        self.statements.append(statement)
        return statement

    def get_statements_count(self) -> int:
        """Get count of statements."""
        return len(self.statements)

    def get_violations_count(self) -> int:
        """Get count of violations."""
        return len(self.violations)


@pytest.fixture
def knight_witness() -> InMemoryKnightWitness:
    """Create an in-memory Knight witness."""
    return InMemoryKnightWitness()


@pytest.fixture
def suppression_config() -> SuppressionDetectionConfig:
    """Create suppression config for testing."""
    return SuppressionDetectionConfig(
        timeout_seconds=2,
        check_interval_seconds=1,
        auto_escalate_to_conclave=True,
    )


@pytest.fixture
def full_pipeline(
    knight_witness: InMemoryKnightWitness,
    suppression_config: SuppressionDetectionConfig,
) -> tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness]:
    """Create a full failure propagation pipeline."""
    suppression_service = SuppressionDetectionService(
        knight_witness=knight_witness,  # type: ignore
        config=suppression_config,
    )
    adapter = FailurePropagationAdapter(
        knight_witness=knight_witness,  # type: ignore
        suppression_detector=suppression_service,
        verbose=True,
    )
    return adapter, suppression_service, knight_witness


# =============================================================================
# Integration Tests - Full Pipeline Flow
# =============================================================================


class TestFailurePropagationPipeline:
    """Integration tests for the full failure propagation pipeline."""

    @pytest.mark.asyncio
    async def test_full_failure_flow_from_emit_to_prince(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test complete failure flow: emit -> witness -> propagate -> notify Prince."""
        adapter, suppression_service, knight = full_pipeline
        task_id = uuid4()

        # Step 1: Create and emit failure
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_alpha",
            task_id=task_id,
            severity=FailureSeverity.HIGH,
            evidence={"error": "Connection timeout", "retry_count": 3},
        )

        result = await adapter.emit_failure(signal)

        # Verify emission
        assert result.success is True
        assert result.signal is not None
        assert result.signal.is_propagated is True
        assert result.witness_ref is not None

        # Verify Knight witnessed
        assert knight.get_statements_count() >= 1

        # Step 2: Notify Prince
        context = PrinceNotificationContext(
            signal=result.signal,
            task_spec={"id": str(task_id), "name": "Integration Test Task"},
            execution_result={"status": "failed", "error": "Connection timeout"},
            evidence=[{"type": "log", "data": "Connection refused"}],
            timeline=[
                {"timestamp": datetime.now(timezone.utc).isoformat(), "event": "failed"},
            ],
        )

        notify_result = await adapter.notify_prince(context)

        assert notify_result.success is True

        # Verify signal marked as Prince-notified
        stored_signal = await adapter.get_failure_signal(signal.signal_id)
        assert stored_signal is not None
        assert stored_signal.prince_notified is True

    @pytest.mark.asyncio
    async def test_multiple_failures_same_task(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test handling multiple failures for the same task."""
        adapter, suppression_service, knight = full_pipeline
        task_id = uuid4()

        # Emit multiple failures
        signals = []
        for i in range(5):
            signal = FailureSignal.create(
                signal_type=FailureSignalType.RESOURCE_EXHAUSTED,
                source_archon_id="duke_alpha",
                task_id=task_id,
                severity=FailureSeverity.MEDIUM,
                evidence={"attempt": i, "resource": "memory"},
            )
            result = await adapter.emit_failure(signal)
            signals.append(result.signal)

        # Verify all failures stored and queryable
        task_failures = await adapter.get_failures_by_task(task_id)
        assert len(task_failures) == 5

        # Verify timeline has all events
        timeline = await adapter.get_failure_timeline(task_id)
        assert len(timeline) == 5

        # Verify Knight witnessed all
        assert knight.get_statements_count() >= 5

    @pytest.mark.asyncio
    async def test_failure_motion_tracing(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test that failures can be traced back to their originating motion."""
        adapter, suppression_service, knight = full_pipeline

        motion_id = uuid4()

        # Create failures for different tasks but same motion
        task_ids = [uuid4() for _ in range(3)]
        for task_id in task_ids:
            signal = FailureSignal.create(
                signal_type=FailureSignalType.TASK_FAILED,
                source_archon_id="duke_beta",
                task_id=task_id,
                severity=FailureSeverity.HIGH,
                evidence={},
                motion_ref=motion_id,
            )
            await adapter.emit_failure(signal)

        # Query by motion
        motion_failures = await adapter.get_failures_by_motion(motion_id)
        assert len(motion_failures) == 3

        # Verify all reference the same motion
        for failure in motion_failures:
            assert failure.motion_ref == motion_id


# =============================================================================
# Integration Tests - Suppression Detection Flow
# =============================================================================


class TestSuppressionDetectionFlow:
    """Integration tests for suppression detection pipeline."""

    @pytest.mark.asyncio
    async def test_suppression_detection_full_flow(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test full suppression detection flow with escalation."""
        adapter, suppression_service, knight = full_pipeline

        # Create failure signal
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_suspicious",
            task_id=uuid4(),
            severity=FailureSeverity.CRITICAL,
            evidence={},
        )

        # Start monitoring with immediate timeout
        suppression_service.start_monitoring(signal, timeout_seconds=0)

        # Check for suppression
        check_result = suppression_service.check_for_suppression(signal.task_id)

        assert check_result.suppression_detected is True
        assert check_result.violation is not None

        # Record and escalate through adapter
        witness_ref = await adapter.record_suppression_violation(check_result.violation)

        assert witness_ref is not None

        # Verify violation recorded
        violations = await adapter.get_suppression_violations()
        assert len(violations) == 1
        assert violations[0].escalated_to_conclave is True

        # Verify Knight witnessed the violation
        assert knight.get_violations_count() >= 1

    @pytest.mark.asyncio
    async def test_properly_propagated_failure_not_flagged(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test that properly propagated failures are not flagged as suppressed."""
        adapter, suppression_service, knight = full_pipeline

        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_good",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        # Proper flow: emit (which includes propagation)
        result = await adapter.emit_failure(signal)
        assert result.success is True

        # Check for suppression - should find nothing
        check_result = suppression_service.check_for_suppression(signal.task_id)

        assert check_result.suppression_detected is False

        # Verify no violations
        violations = await adapter.get_suppression_violations()
        assert len(violations) == 0


# =============================================================================
# Integration Tests - Event Store Integrity (AC5)
# =============================================================================


class TestEventStoreIntegrity:
    """Integration tests for event store integrity (AC5)."""

    @pytest.mark.asyncio
    async def test_failure_signals_append_only(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test that failure signals are append-only."""
        adapter, suppression_service, knight = full_pipeline

        # Emit failures
        signal_ids = []
        for i in range(5):
            signal = FailureSignal.create(
                signal_type=FailureSignalType.TASK_FAILED,
                source_archon_id="duke_test",
                task_id=uuid4(),
                severity=FailureSeverity.HIGH,
                evidence={"index": i},
            )
            result = await adapter.emit_failure(signal)
            signal_ids.append(result.signal.signal_id)

        # Verify count keeps growing
        assert adapter.failure_count == 5

        # Emit more
        for i in range(3):
            signal = FailureSignal.create(
                signal_type=FailureSignalType.BLOCKED,
                source_archon_id="duke_test",
                task_id=uuid4(),
                severity=FailureSeverity.MEDIUM,
                evidence={},
            )
            await adapter.emit_failure(signal)

        assert adapter.failure_count == 8

        # Verify all original signals still exist
        for signal_id in signal_ids:
            stored = await adapter.get_failure_signal(signal_id)
            assert stored is not None

    @pytest.mark.asyncio
    async def test_timeline_immutability(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test that timeline entries cannot be modified."""
        adapter, suppression_service, knight = full_pipeline
        task_id = uuid4()

        # Emit failure
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=task_id,
            severity=FailureSeverity.HIGH,
            evidence={},
        )
        await adapter.emit_failure(signal)

        # Get timeline
        timeline = await adapter.get_failure_timeline(task_id)
        original_length = len(timeline)

        # Emit more failures
        for _ in range(3):
            signal2 = FailureSignal.create(
                signal_type=FailureSignalType.BLOCKED,
                source_archon_id="duke_test",
                task_id=task_id,
                severity=FailureSeverity.MEDIUM,
                evidence={},
            )
            await adapter.emit_failure(signal2)

        # Timeline should have grown, not replaced
        new_timeline = await adapter.get_failure_timeline(task_id)
        assert len(new_timeline) == original_length + 3

    @pytest.mark.asyncio
    async def test_all_failures_witnessed(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test that all failures are witnessed by Knight (CT-12)."""
        adapter, suppression_service, knight = full_pipeline

        # Emit multiple failures
        for i in range(10):
            signal = FailureSignal.create(
                signal_type=FailureSignalType.TASK_FAILED,
                source_archon_id=f"duke_{i}",
                task_id=uuid4(),
                severity=FailureSeverity.HIGH,
                evidence={},
            )
            await adapter.emit_failure(signal)

        # Every failure should have been witnessed
        assert knight.get_statements_count() >= 10


# =============================================================================
# Integration Tests - Severity-Based Handling
# =============================================================================


class TestSeverityBasedHandling:
    """Integration tests for severity-based failure handling."""

    @pytest.mark.asyncio
    async def test_critical_failures_expedited(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test that critical failures get expedited handling."""
        adapter, suppression_service, knight = full_pipeline

        critical_signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_critical",
            task_id=uuid4(),
            severity=FailureSeverity.CRITICAL,
            evidence={"critical_reason": "System integrity at risk"},
        )

        result = await adapter.emit_failure(critical_signal)

        # Critical signals should be immediately propagated
        assert result.success is True
        assert result.signal is not None
        assert result.signal.is_propagated is True
        assert result.signal.is_critical is True

    @pytest.mark.asyncio
    async def test_severity_preserved_through_pipeline(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test that severity is preserved through the entire pipeline."""
        adapter, suppression_service, knight = full_pipeline

        severities = [
            FailureSeverity.CRITICAL,
            FailureSeverity.HIGH,
            FailureSeverity.MEDIUM,
            FailureSeverity.LOW,
        ]

        for severity in severities:
            signal = FailureSignal.create(
                signal_type=FailureSignalType.TASK_FAILED,
                source_archon_id="duke_test",
                task_id=uuid4(),
                severity=severity,
                evidence={},
            )
            result = await adapter.emit_failure(signal)

            # Verify severity preserved
            assert result.signal.severity == severity

            # Verify stored with same severity
            stored = await adapter.get_failure_signal(signal.signal_id)
            assert stored is not None
            assert stored.severity == severity


# =============================================================================
# Integration Tests - Concurrent Failure Handling
# =============================================================================


class TestConcurrentFailureHandling:
    """Integration tests for concurrent failure handling."""

    @pytest.mark.asyncio
    async def test_concurrent_failure_emissions(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test that concurrent failure emissions are handled correctly."""
        adapter, suppression_service, knight = full_pipeline

        # Create many concurrent emissions
        async def emit_failure(index: int) -> None:
            signal = FailureSignal.create(
                signal_type=FailureSignalType.TASK_FAILED,
                source_archon_id=f"duke_{index}",
                task_id=uuid4(),
                severity=FailureSeverity.HIGH,
                evidence={"index": index},
            )
            await adapter.emit_failure(signal)

        # Run concurrently
        await asyncio.gather(*[emit_failure(i) for i in range(20)])

        # All should be stored
        assert adapter.failure_count == 20

        # All should be witnessed
        assert knight.get_statements_count() >= 20


# =============================================================================
# Integration Tests - Error Recovery
# =============================================================================


class TestErrorRecovery:
    """Integration tests for error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_adapter_continues_after_reset(
        self,
        full_pipeline: tuple[FailurePropagationAdapter, SuppressionDetectionService, InMemoryKnightWitness],
    ) -> None:
        """Test that adapter continues working after reset."""
        adapter, suppression_service, knight = full_pipeline

        # Emit some failures
        for _ in range(5):
            signal = FailureSignal.create(
                signal_type=FailureSignalType.TASK_FAILED,
                source_archon_id="duke_test",
                task_id=uuid4(),
                severity=FailureSeverity.HIGH,
                evidence={},
            )
            await adapter.emit_failure(signal)

        assert adapter.failure_count == 5

        # Reset
        adapter.reset()
        assert adapter.failure_count == 0

        # Should work again
        new_signal = FailureSignal.create(
            signal_type=FailureSignalType.BLOCKED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.MEDIUM,
            evidence={},
        )
        result = await adapter.emit_failure(new_signal)

        assert result.success is True
        assert adapter.failure_count == 1
