"""Unit tests for Failure Propagation (Story GOV-4.3).

Tests the failure signal domain models, failure propagation port,
suppression detection service, and failure propagation adapter.

Per Government PRD:
- FR-GOV-13: Duke/Earl constraints - No suppression of failure signals
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.failure_propagation import (
    FailurePropagationProtocol,
    FailureSeverity,
    FailureSignal,
    FailureSignalType,
    PrinceNotificationContext,
    PropagationResult,
    SuppressionCheckResult,
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
    MonitoredFailure,
    SuppressionDetectionConfig,
    SuppressionDetectionService,
)
from src.infrastructure.adapters.government.failure_propagation_adapter import (
    FailurePropagationAdapter,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_knight_witness() -> MagicMock:
    """Create a mock Knight witness."""
    witness = MagicMock(spec=KnightWitnessProtocol)

    def create_statement(ctx: ObservationContext) -> WitnessStatement:
        return WitnessStatement.create(
            statement_type=WitnessStatementType.PROCEDURAL_TRANSITION,
            description="Test observation",
            roles_involved=["test"],
        )

    def record_violation(v: ViolationRecord) -> WitnessStatement:
        return WitnessStatement.create(
            statement_type=WitnessStatementType.ROLE_VIOLATION,
            description=v.description,
            roles_involved=[v.violator_name],
        )

    witness.observe.side_effect = create_statement
    witness.record_violation.side_effect = record_violation
    return witness


@pytest.fixture
def suppression_config() -> SuppressionDetectionConfig:
    """Create a suppression detection config with short timeout for testing."""
    return SuppressionDetectionConfig(
        timeout_seconds=1,  # 1 second for fast tests
        check_interval_seconds=1,
        auto_escalate_to_conclave=True,
        critical_timeout_multiplier=0.5,
    )


@pytest.fixture
def suppression_service(
    mock_knight_witness: MagicMock,
    suppression_config: SuppressionDetectionConfig,
) -> SuppressionDetectionService:
    """Create a suppression detection service."""
    return SuppressionDetectionService(
        knight_witness=mock_knight_witness,
        config=suppression_config,
    )


@pytest.fixture
def failure_adapter(
    mock_knight_witness: MagicMock,
    suppression_service: SuppressionDetectionService,
) -> FailurePropagationAdapter:
    """Create a failure propagation adapter."""
    return FailurePropagationAdapter(
        knight_witness=mock_knight_witness,
        suppression_detector=suppression_service,
        verbose=True,
    )


@pytest.fixture
def sample_failure_signal() -> FailureSignal:
    """Create a sample failure signal."""
    return FailureSignal.create(
        signal_type=FailureSignalType.TASK_FAILED,
        source_archon_id="duke_test",
        task_id=uuid4(),
        severity=FailureSeverity.HIGH,
        evidence={
            "error": "Test failure",
            "stack_trace": "...",
        },
    )


# =============================================================================
# AC1: Immediate Failure Propagation Tests
# =============================================================================


class TestImmediateFailurePropagation:
    """Tests for AC1: Immediate failure propagation."""

    @pytest.mark.asyncio
    async def test_failure_propagation_is_immediate(
        self,
        failure_adapter: FailurePropagationAdapter,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that failures are propagated immediately."""
        result = await failure_adapter.emit_failure(sample_failure_signal)

        assert result.success is True
        assert result.signal is not None
        assert result.signal.is_propagated is True
        assert result.signal.propagated_at is not None

    @pytest.mark.asyncio
    async def test_failure_is_witnessed_before_propagation(
        self,
        failure_adapter: FailurePropagationAdapter,
        mock_knight_witness: MagicMock,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that Knight witnesses failure before propagation (CT-12)."""
        result = await failure_adapter.emit_failure(sample_failure_signal)

        # Knight should have witnessed the failure
        mock_knight_witness.observe.assert_called_once()
        assert result.witness_ref is not None

    @pytest.mark.asyncio
    async def test_propagated_signal_has_witness_reference(
        self,
        failure_adapter: FailurePropagationAdapter,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that propagated signal includes witness reference."""
        result = await failure_adapter.emit_failure(sample_failure_signal)

        assert result.signal is not None
        assert result.signal.witness_ref is not None


# =============================================================================
# AC2: Suppression Detection Tests
# =============================================================================


class TestSuppressionDetection:
    """Tests for AC2: Suppression detection."""

    def test_suppression_service_initializes(
        self,
        suppression_service: SuppressionDetectionService,
    ) -> None:
        """Test suppression service initialization."""
        assert suppression_service.monitored_count == 0
        assert suppression_service.violation_count == 0

    def test_start_monitoring_tracks_failure(
        self,
        suppression_service: SuppressionDetectionService,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that starting monitoring tracks the failure."""
        monitored = suppression_service.start_monitoring(sample_failure_signal)

        assert monitored.signal == sample_failure_signal
        assert monitored.timeout_at is not None
        assert suppression_service.monitored_count == 1

    def test_mark_propagated_removes_from_monitoring(
        self,
        suppression_service: SuppressionDetectionService,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that marking propagated removes from monitoring."""
        suppression_service.start_monitoring(sample_failure_signal)
        assert suppression_service.monitored_count == 1

        result = suppression_service.mark_propagated(sample_failure_signal.signal_id)

        assert result is True
        assert suppression_service.monitored_count == 0

    def test_suppression_detected_on_timeout(
        self,
        suppression_service: SuppressionDetectionService,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that suppression is detected when timeout expires."""
        # Start monitoring with very short timeout
        suppression_service.start_monitoring(
            sample_failure_signal,
            timeout_seconds=0,  # Immediate timeout
        )

        # Check for suppression (should detect immediately)
        result = suppression_service.check_for_suppression(
            sample_failure_signal.task_id
        )

        assert result.suppression_detected is True
        assert result.violation is not None
        assert result.violation.detection_method == SuppressionDetectionMethod.TIMEOUT

    def test_suppression_violation_has_correct_archon(
        self,
        suppression_service: SuppressionDetectionService,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that suppression violation identifies the suppressing archon."""
        suppression_service.start_monitoring(
            sample_failure_signal,
            timeout_seconds=0,
        )

        result = suppression_service.check_for_suppression(
            sample_failure_signal.task_id
        )

        assert result.violation is not None
        assert result.violation.suppressing_archon_id == sample_failure_signal.source_archon_id

    def test_explicit_suppression_attempt_recorded(
        self,
        suppression_service: SuppressionDetectionService,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test recording explicit suppression attempts."""
        violation = suppression_service.record_suppression_attempt(
            signal_id=sample_failure_signal.signal_id,
            suppressing_archon_id="malicious_duke",
            task_id=sample_failure_signal.task_id,
            method=SuppressionDetectionMethod.MANUAL_OVERRIDE,
            evidence={"reason": "Attempted to hide failure"},
        )

        assert violation.detection_method == SuppressionDetectionMethod.MANUAL_OVERRIDE
        assert violation.suppressing_archon_id == "malicious_duke"
        assert suppression_service.violation_count == 1


# =============================================================================
# AC3: Failure Signal Types Tests
# =============================================================================


class TestFailureSignalTypes:
    """Tests for AC3: Failure signal types."""

    @pytest.mark.parametrize(
        "signal_type",
        [
            FailureSignalType.TASK_FAILED,
            FailureSignalType.CONSTRAINT_VIOLATED,
            FailureSignalType.RESOURCE_EXHAUSTED,
            FailureSignalType.TIMEOUT,
            FailureSignalType.BLOCKED,
            FailureSignalType.INTENT_AMBIGUITY,
        ],
    )
    def test_all_signal_types_supported(
        self,
        signal_type: FailureSignalType,
    ) -> None:
        """Test that all specified signal types are supported."""
        signal = FailureSignal.create(
            signal_type=signal_type,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={"test": True},
        )

        assert signal.signal_type == signal_type

    @pytest.mark.parametrize(
        "severity",
        [
            FailureSeverity.CRITICAL,
            FailureSeverity.HIGH,
            FailureSeverity.MEDIUM,
            FailureSeverity.LOW,
        ],
    )
    def test_all_severity_levels_supported(
        self,
        severity: FailureSeverity,
    ) -> None:
        """Test that all severity levels are supported."""
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=severity,
            evidence={"test": True},
        )

        assert signal.severity == severity

    def test_failure_signal_has_required_fields(
        self,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that failure signal has all required fields per AC3."""
        # Per AC3: signal_type
        assert sample_failure_signal.signal_type is not None

        # Per AC3: source_archon_id
        assert sample_failure_signal.source_archon_id is not None

        # Per AC3: task_id
        assert sample_failure_signal.task_id is not None

        # Per AC3: evidence
        assert sample_failure_signal.evidence is not None

        # Per AC3: severity
        assert sample_failure_signal.severity is not None

        # Per AC3: detected_at
        assert sample_failure_signal.detected_at is not None

    def test_failure_signal_to_dict(
        self,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test failure signal serialization."""
        data = sample_failure_signal.to_dict()

        assert "signal_id" in data
        assert "signal_type" in data
        assert "source_archon_id" in data
        assert "task_id" in data
        assert "severity" in data
        assert "evidence" in data
        assert "detected_at" in data


# =============================================================================
# AC4: Prince Notification Tests
# =============================================================================


class TestPrinceNotification:
    """Tests for AC4: Prince notification with full context."""

    @pytest.mark.asyncio
    async def test_prince_receives_full_context(
        self,
        failure_adapter: FailurePropagationAdapter,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that Prince receives full context for evaluation."""
        # First emit the failure
        await failure_adapter.emit_failure(sample_failure_signal)

        # Create notification context
        context = PrinceNotificationContext(
            signal=sample_failure_signal,
            task_spec={"id": str(sample_failure_signal.task_id), "name": "Test Task"},
            execution_result={"status": "failed", "error": "Test error"},
            evidence=[{"type": "log", "data": "Error occurred"}],
            timeline=[
                {"timestamp": "2024-01-01T00:00:00Z", "event": "started"},
                {"timestamp": "2024-01-01T00:01:00Z", "event": "failed"},
            ],
        )

        result = await failure_adapter.notify_prince(context)

        assert result.success is True
        assert result.prince_id is not None

    @pytest.mark.asyncio
    async def test_prince_notification_marks_signal(
        self,
        failure_adapter: FailurePropagationAdapter,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that notifying Prince marks the signal."""
        await failure_adapter.emit_failure(sample_failure_signal)

        context = PrinceNotificationContext(
            signal=sample_failure_signal,
            task_spec={},
            execution_result={},
            evidence=[],
            timeline=[],
        )

        await failure_adapter.notify_prince(context)

        # Retrieve the signal and check it's marked
        stored_signal = await failure_adapter.get_failure_signal(
            sample_failure_signal.signal_id
        )
        assert stored_signal is not None
        assert stored_signal.prince_notified is True

    def test_notification_context_includes_task_spec(self) -> None:
        """Test that notification context includes AegisTaskSpec."""
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        task_spec = {
            "id": str(signal.task_id),
            "name": "Test Task",
            "constraints": ["no_external_calls"],
        }

        context = PrinceNotificationContext(
            signal=signal,
            task_spec=task_spec,
            execution_result={},
            evidence=[],
            timeline=[],
        )

        assert context.task_spec == task_spec

    def test_notification_context_includes_timeline(self) -> None:
        """Test that notification context includes timeline."""
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        timeline = [
            {"timestamp": "2024-01-01T00:00:00Z", "event": "task_started"},
            {"timestamp": "2024-01-01T00:00:30Z", "event": "resource_acquired"},
            {"timestamp": "2024-01-01T00:01:00Z", "event": "execution_failed"},
        ]

        context = PrinceNotificationContext(
            signal=signal,
            task_spec={},
            execution_result={},
            evidence=[],
            timeline=timeline,
        )

        assert len(context.timeline) == 3


# =============================================================================
# AC5: Failure Chain Integrity Tests
# =============================================================================


class TestFailureChainIntegrity:
    """Tests for AC5: Failure chain integrity."""

    @pytest.mark.asyncio
    async def test_failure_stored_in_event_store(
        self,
        failure_adapter: FailurePropagationAdapter,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that failure is stored (simulating event store)."""
        await failure_adapter.emit_failure(sample_failure_signal)

        # Retrieve from storage
        stored = await failure_adapter.get_failure_signal(
            sample_failure_signal.signal_id
        )

        assert stored is not None
        assert stored.signal_id == sample_failure_signal.signal_id

    @pytest.mark.asyncio
    async def test_failures_queryable_by_task(
        self,
        failure_adapter: FailurePropagationAdapter,
    ) -> None:
        """Test that failures can be queried by task."""
        task_id = uuid4()

        # Emit multiple failures for same task
        for i in range(3):
            signal = FailureSignal.create(
                signal_type=FailureSignalType.TASK_FAILED,
                source_archon_id="duke_test",
                task_id=task_id,
                severity=FailureSeverity.HIGH,
                evidence={"attempt": i},
            )
            await failure_adapter.emit_failure(signal)

        # Query by task
        failures = await failure_adapter.get_failures_by_task(task_id)

        assert len(failures) == 3

    @pytest.mark.asyncio
    async def test_failures_queryable_by_motion(
        self,
        failure_adapter: FailurePropagationAdapter,
    ) -> None:
        """Test that failures can be queried by motion."""
        motion_ref = uuid4()

        # Emit failures with motion reference
        for i in range(2):
            signal = FailureSignal.create(
                signal_type=FailureSignalType.TASK_FAILED,
                source_archon_id="duke_test",
                task_id=uuid4(),
                severity=FailureSeverity.HIGH,
                evidence={},
                motion_ref=motion_ref,
            )
            await failure_adapter.emit_failure(signal)

        # Query by motion
        failures = await failure_adapter.get_failures_by_motion(motion_ref)

        assert len(failures) == 2

    @pytest.mark.asyncio
    async def test_failure_witnessed_by_knight(
        self,
        failure_adapter: FailurePropagationAdapter,
        mock_knight_witness: MagicMock,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that failure is witnessed by Knight per CT-12."""
        await failure_adapter.emit_failure(sample_failure_signal)

        mock_knight_witness.observe.assert_called_once()
        call_args = mock_knight_witness.observe.call_args[0][0]
        assert call_args.event_type == "failure_signal_emitted"
        assert str(sample_failure_signal.task_id) in call_args.target_id


# =============================================================================
# AC6: Anti-Suppression Enforcement Tests
# =============================================================================


class TestAntiSuppressionEnforcement:
    """Tests for AC6: Anti-suppression enforcement."""

    def test_suppression_violation_auto_generated_on_timeout(
        self,
        suppression_service: SuppressionDetectionService,
    ) -> None:
        """Test that suppression violation is auto-generated on timeout."""
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        # Start monitoring with immediate timeout
        suppression_service.start_monitoring(signal, timeout_seconds=0)

        # Check should detect violation
        result = suppression_service.check_for_suppression(signal.task_id)

        assert result.suppression_detected is True
        assert result.violation is not None

    def test_suppression_violation_escalated_to_conclave(
        self,
        suppression_service: SuppressionDetectionService,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test that suppression violations are escalated to Conclave."""
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.CRITICAL,
            evidence={},
        )

        suppression_service.start_monitoring(signal, timeout_seconds=0)
        result = suppression_service.check_for_suppression(signal.task_id)

        assert result.violation is not None

        # Witness and escalate
        witness_ref = suppression_service.witness_violation(result.violation)
        escalated = suppression_service.escalate_to_conclave(
            result.violation, witness_ref
        )

        assert escalated.escalated_to_conclave is True
        assert escalated.witness_ref == witness_ref

    @pytest.mark.asyncio
    async def test_suppression_violation_recorded_in_adapter(
        self,
        failure_adapter: FailurePropagationAdapter,
    ) -> None:
        """Test that suppression violations are recorded."""
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        violation = SuppressionViolation.create(
            signal_id=signal.signal_id,
            suppressing_archon_id="duke_test",
            detection_method=SuppressionDetectionMethod.TIMEOUT,
            task_id=signal.task_id,
        )

        witness_ref = await failure_adapter.record_suppression_violation(violation)

        assert witness_ref is not None

        # Verify it's stored
        violations = await failure_adapter.get_suppression_violations()
        assert len(violations) == 1

    @pytest.mark.asyncio
    async def test_suppression_violations_queryable_by_archon(
        self,
        failure_adapter: FailurePropagationAdapter,
    ) -> None:
        """Test that violations can be queried by archon."""
        # Record violations for different archons
        for archon_id in ["duke_a", "duke_b", "duke_a"]:
            violation = SuppressionViolation.create(
                signal_id=uuid4(),
                suppressing_archon_id=archon_id,
                detection_method=SuppressionDetectionMethod.TIMEOUT,
                task_id=uuid4(),
            )
            await failure_adapter.record_suppression_violation(violation)

        # Query for specific archon
        violations = await failure_adapter.get_suppression_violations(
            archon_id="duke_a"
        )

        assert len(violations) == 2


# =============================================================================
# Domain Model Tests
# =============================================================================


class TestFailureSignalDomainModel:
    """Tests for FailureSignal domain model."""

    def test_failure_signal_create(self) -> None:
        """Test creating a failure signal."""
        task_id = uuid4()
        signal = FailureSignal.create(
            signal_type=FailureSignalType.CONSTRAINT_VIOLATED,
            source_archon_id="duke_alpha",
            task_id=task_id,
            severity=FailureSeverity.CRITICAL,
            evidence={"constraint": "memory_limit", "used": 512, "limit": 256},
        )

        assert signal.signal_id is not None
        assert signal.signal_type == FailureSignalType.CONSTRAINT_VIOLATED
        assert signal.source_archon_id == "duke_alpha"
        assert signal.task_id == task_id
        assert signal.severity == FailureSeverity.CRITICAL
        assert signal.is_propagated is False
        assert signal.prince_notified is False

    def test_failure_signal_immutable(self) -> None:
        """Test that failure signal is immutable."""
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        with pytest.raises(AttributeError):
            signal.severity = FailureSeverity.LOW  # type: ignore

    def test_failure_signal_with_propagation(self) -> None:
        """Test marking signal as propagated."""
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        assert signal.is_propagated is False

        witness_ref = uuid4()
        propagated = signal.with_propagation(witness_ref)

        assert propagated.is_propagated is True
        assert propagated.propagated_at is not None
        assert propagated.witness_ref == witness_ref
        # Original unchanged
        assert signal.is_propagated is False

    def test_failure_signal_with_prince_notification(self) -> None:
        """Test marking signal as Prince-notified."""
        signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        assert signal.prince_notified is False

        notified = signal.with_prince_notification()

        assert notified.prince_notified is True
        # Original unchanged
        assert signal.prince_notified is False

    def test_is_critical_property(self) -> None:
        """Test is_critical property."""
        critical = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.CRITICAL,
            evidence={},
        )

        high = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        assert critical.is_critical is True
        assert high.is_critical is False


class TestSuppressionViolationDomainModel:
    """Tests for SuppressionViolation domain model."""

    def test_suppression_violation_create(self) -> None:
        """Test creating a suppression violation."""
        signal_id = uuid4()
        task_id = uuid4()
        violation = SuppressionViolation.create(
            signal_id=signal_id,
            suppressing_archon_id="duke_bad",
            detection_method=SuppressionDetectionMethod.TIMEOUT,
            task_id=task_id,
            evidence={"timeout_seconds": 30, "elapsed": 45},
        )

        assert violation.violation_id is not None
        assert violation.signal_id == signal_id
        assert violation.suppressing_archon_id == "duke_bad"
        assert violation.detection_method == SuppressionDetectionMethod.TIMEOUT
        assert violation.escalated_to_conclave is False

    def test_suppression_violation_immutable(self) -> None:
        """Test that suppression violation is immutable."""
        violation = SuppressionViolation.create(
            signal_id=uuid4(),
            suppressing_archon_id="duke_test",
            detection_method=SuppressionDetectionMethod.TIMEOUT,
            task_id=uuid4(),
        )

        with pytest.raises(AttributeError):
            violation.escalated_to_conclave = True  # type: ignore

    def test_suppression_violation_with_escalation(self) -> None:
        """Test marking violation as escalated."""
        violation = SuppressionViolation.create(
            signal_id=uuid4(),
            suppressing_archon_id="duke_test",
            detection_method=SuppressionDetectionMethod.TIMEOUT,
            task_id=uuid4(),
        )

        witness_ref = uuid4()
        escalated = violation.with_escalation(witness_ref)

        assert escalated.escalated_to_conclave is True
        assert escalated.witness_ref == witness_ref
        # Original unchanged
        assert violation.escalated_to_conclave is False

    def test_suppression_violation_to_dict(self) -> None:
        """Test suppression violation serialization."""
        violation = SuppressionViolation.create(
            signal_id=uuid4(),
            suppressing_archon_id="duke_test",
            detection_method=SuppressionDetectionMethod.MANUAL_OVERRIDE,
            task_id=uuid4(),
        )

        data = violation.to_dict()

        assert "violation_id" in data
        assert "signal_id" in data
        assert "suppressing_archon_id" in data
        assert "detection_method" in data
        assert "detected_at" in data
        assert data["detection_method"] == "manual_override"


# =============================================================================
# Timeline Tests
# =============================================================================


class TestFailureTimeline:
    """Tests for failure timeline functionality."""

    @pytest.mark.asyncio
    async def test_timeline_tracks_events(
        self,
        failure_adapter: FailurePropagationAdapter,
        sample_failure_signal: FailureSignal,
    ) -> None:
        """Test that timeline tracks failure events."""
        await failure_adapter.emit_failure(sample_failure_signal)

        timeline = await failure_adapter.get_failure_timeline(
            sample_failure_signal.task_id
        )

        assert len(timeline) >= 1
        assert any(e["event_type"] == "failure_emitted" for e in timeline)

    @pytest.mark.asyncio
    async def test_timeline_in_chronological_order(
        self,
        failure_adapter: FailurePropagationAdapter,
    ) -> None:
        """Test that timeline is in chronological order."""
        task_id = uuid4()

        # Emit multiple events
        for i in range(3):
            signal = FailureSignal.create(
                signal_type=FailureSignalType.TASK_FAILED,
                source_archon_id="duke_test",
                task_id=task_id,
                severity=FailureSeverity.HIGH,
                evidence={"attempt": i},
            )
            await failure_adapter.emit_failure(signal)

        timeline = await failure_adapter.get_failure_timeline(task_id)

        # Verify chronological order
        timestamps = [e["timestamp"] for e in timeline]
        assert timestamps == sorted(timestamps)


# =============================================================================
# Critical Timeout Handling Tests
# =============================================================================


class TestCriticalTimeoutHandling:
    """Tests for critical failure timeout handling."""

    def test_critical_failures_have_shorter_timeout(
        self,
        suppression_service: SuppressionDetectionService,
    ) -> None:
        """Test that critical failures have shorter timeout."""
        critical_signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.CRITICAL,
            evidence={},
        )

        high_signal = FailureSignal.create(
            signal_type=FailureSignalType.TASK_FAILED,
            source_archon_id="duke_test",
            task_id=uuid4(),
            severity=FailureSeverity.HIGH,
            evidence={},
        )

        critical_monitored = suppression_service.start_monitoring(critical_signal)
        high_monitored = suppression_service.start_monitoring(high_signal)

        # Critical should have shorter timeout
        assert critical_monitored.timeout_at is not None
        assert high_monitored.timeout_at is not None
        assert critical_monitored.timeout_at < high_monitored.timeout_at
