"""Integration tests for Pre-mortem Operational Failure Prevention (Story 8.8, FR106-FR107).

Tests for the failure prevention feature including:
- AC1: Failure mode registry with pre-mortem modes (VAL-*, PV-*)
- AC2: Early warning alerts when thresholds approached
- AC3: Health status dashboard for all modes
- AC4: Query performance monitoring (FR106: 30s SLA for <10k events)
- AC5: Load shedding decisions (FR107: constitutional events NEVER shed)
- AC6: Pattern violation detection from FMEA risk matrix

Constitutional Constraints:
- FR106: Historical queries SHALL complete within 30 seconds for <10k events
- FR107: Constitutional events NEVER shed under load
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All warnings witnessed
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.failure_prevention_service import (
    FailurePreventionService,
)
from src.application.services.load_shedding_service import (
    DEFAULT_CAPACITY_THRESHOLD,
    LoadSheddingService,
)
from src.application.services.query_performance_service import (
    QUERY_SLA_THRESHOLD_EVENTS,
    QUERY_SLA_TIMEOUT_SECONDS,
    QueryPerformanceService,
)
from src.application.services.pattern_violation_service import (
    PatternViolationService,
)
from src.domain.errors.failure_prevention import (
    ConstitutionalEventSheddingError,
    FailureModeViolationError,
    QueryPerformanceViolationError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.failure_mode import (
    DEFAULT_FAILURE_MODES,
    EarlyWarning,
    FailureMode,
    FailureModeId,
    FailureModeSeverity,
    FailureModeStatus,
    FailureModeThreshold,
)
from src.domain.models.pattern_violation import (
    PatternViolationType,
)
from src.infrastructure.stubs.failure_mode_registry_stub import (
    FailureModeRegistryStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


class TestFailureModeRegistry:
    """Integration tests for AC1: Failure mode registry with pre-mortem modes."""

    @pytest.mark.asyncio
    async def test_all_val_modes_registered(self) -> None:
        """Test that all VAL-* failure modes are registered (AC1)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        modes = await service.get_all_failure_modes()
        mode_ids = [m.id for m in modes]

        assert FailureModeId.VAL_1 in mode_ids
        assert FailureModeId.VAL_2 in mode_ids
        assert FailureModeId.VAL_3 in mode_ids
        assert FailureModeId.VAL_4 in mode_ids
        assert FailureModeId.VAL_5 in mode_ids

    @pytest.mark.asyncio
    async def test_all_pv_modes_registered(self) -> None:
        """Test that all PV-* pattern violation modes are registered (AC1)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        modes = await service.get_all_failure_modes()
        mode_ids = [m.id for m in modes]

        assert FailureModeId.PV_001 in mode_ids
        assert FailureModeId.PV_002 in mode_ids
        assert FailureModeId.PV_003 in mode_ids

    @pytest.mark.asyncio
    async def test_val1_is_silent_signature_corruption(self) -> None:
        """Test that VAL-1 is silent signature corruption (AC1)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        mode = await service.get_failure_mode(FailureModeId.VAL_1)

        assert mode is not None
        assert "signature" in mode.description.lower()
        assert mode.severity == FailureModeSeverity.CRITICAL


class TestEarlyWarningAlerts:
    """Integration tests for AC2: Early warning alerts when thresholds approached."""

    @pytest.mark.asyncio
    async def test_warning_generated_when_threshold_breached(self) -> None:
        """Test that early warning is generated when threshold breached (AC2)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        # Configure threshold
        await service.configure_threshold(
            mode_id=FailureModeId.VAL_1,
            metric_name="signature_failures",
            warning_value=3.0,
            critical_value=10.0,
        )

        # Record metric above warning threshold
        status = await service.record_metric(
            FailureModeId.VAL_1,
            "signature_failures",
            5.0,
        )

        assert status == FailureModeStatus.WARNING

        # Check early warning was generated
        warnings = await service.get_early_warnings()
        assert len(warnings) >= 1
        assert warnings[0].mode_id == FailureModeId.VAL_1

    @pytest.mark.asyncio
    async def test_warning_includes_recommended_action(self) -> None:
        """Test that early warning includes recommended action (AC2)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        # Configure and breach threshold
        await service.configure_threshold(
            mode_id=FailureModeId.VAL_1,
            metric_name="test_metric",
            warning_value=3.0,
            critical_value=10.0,
        )
        await service.record_metric(FailureModeId.VAL_1, "test_metric", 5.0)

        warnings = await service.get_early_warnings()

        assert len(warnings) >= 1
        assert warnings[0].recommended_action != ""

    @pytest.mark.asyncio
    async def test_warning_can_be_acknowledged(self) -> None:
        """Test that early warning can be acknowledged (AC2)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        # Add a warning
        warning = EarlyWarning.create(
            mode_id=FailureModeId.VAL_1,
            current_value=5.0,
            threshold=3.0,
            threshold_type="warning",
            recommended_action="Investigate",
            metric_name="test_metric",
        )
        registry.add_warning(warning)

        # Acknowledge it
        success = await service.acknowledge_warning(
            str(warning.warning_id),
            "test_user",
        )

        assert success is True


class TestHealthStatusDashboard:
    """Integration tests for AC3: Health status dashboard for all modes."""

    @pytest.mark.asyncio
    async def test_dashboard_shows_all_modes(self) -> None:
        """Test that dashboard shows all registered failure modes (AC3)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        data = await service.get_dashboard_data()

        assert "failure_modes" in data
        assert len(data["failure_modes"]) == len(DEFAULT_FAILURE_MODES)

    @pytest.mark.asyncio
    async def test_dashboard_shows_overall_status(self) -> None:
        """Test that dashboard shows overall health status (AC3)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        data = await service.get_dashboard_data()

        assert "overall_status" in data
        assert data["overall_status"] == FailureModeStatus.HEALTHY.value

    @pytest.mark.asyncio
    async def test_health_summary_reflects_critical_mode(self) -> None:
        """Test that health summary reflects critical status (AC3)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        # Add critical threshold
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="critical_metric",
            warning_value=3.0,
            critical_value=10.0,
            current_value=15.0,
        )
        registry.add_threshold(threshold)

        summary = await service.get_health_summary()

        assert summary.overall_status == FailureModeStatus.CRITICAL
        assert summary.critical_count >= 1


class TestQueryPerformanceMonitoring:
    """Integration tests for AC4: Query performance monitoring (FR106)."""

    @pytest.mark.asyncio
    async def test_fr106_sla_threshold_is_10k_events(self) -> None:
        """Test that FR106 SLA applies to queries under 10k events (AC4)."""
        assert QUERY_SLA_THRESHOLD_EVENTS == 10000

    @pytest.mark.asyncio
    async def test_fr106_sla_timeout_is_30_seconds(self) -> None:
        """Test that FR106 SLA timeout is 30 seconds (AC4)."""
        assert QUERY_SLA_TIMEOUT_SECONDS == 30.0

    @pytest.mark.asyncio
    async def test_compliant_query_tracking(self) -> None:
        """Test that compliant queries are tracked correctly (AC4)."""
        service = QueryPerformanceService()

        # Start and complete a fast query
        query_id = await service.start_query(event_count=1000)
        compliant = await service.track_query(query_id, event_count=1000, duration_ms=5000.0)

        assert compliant is True

        stats = await service.get_compliance_stats()
        assert stats["total_queries"] == 1
        assert stats["compliant_count"] == 1

    @pytest.mark.asyncio
    async def test_non_compliant_query_detection(self) -> None:
        """Test that non-compliant queries are detected (AC4)."""
        service = QueryPerformanceService()

        # Track a slow query under 10k events
        query_id = await service.start_query(event_count=5000)
        compliant = await service.track_query(
            query_id,
            event_count=5000,
            duration_ms=35000.0,  # 35 seconds, over SLA
        )

        assert compliant is False

        violations = await service.get_recent_violations()
        assert len(violations) == 1

    @pytest.mark.asyncio
    async def test_large_queries_batched(self) -> None:
        """Test that large queries (>10k events) are batched (AC4)."""
        service = QueryPerformanceService()

        # Start a large query
        query_id = await service.start_query(event_count=15000)

        # Verify batch progress is tracked
        progress = await service.get_batch_progress(query_id)
        assert progress is not None
        assert progress.total_events == 15000

    @pytest.mark.asyncio
    async def test_raises_on_sla_violation(self) -> None:
        """Test that raise_if_non_compliant raises on SLA violation (AC4)."""
        service = QueryPerformanceService()

        with pytest.raises(QueryPerformanceViolationError):
            await service.raise_if_non_compliant(
                query_id="test",
                event_count=5000,
                duration_seconds=35.0,
            )


class TestLoadSheddingDecisions:
    """Integration tests for AC5: Load shedding decisions (FR107)."""

    @pytest.mark.asyncio
    async def test_fr107_constitutional_events_never_shed(self) -> None:
        """Test that constitutional events are NEVER shed (FR107, AC5)."""
        service = LoadSheddingService()

        # Set extremely high load
        await service.update_load(99.0)

        # Constitutional events should NEVER be shed
        decision = await service.make_shedding_decision(
            item_type="breach_declaration",
            is_constitutional=True,
        )

        assert decision.was_shed is False
        assert "FR107" in decision.reason

    @pytest.mark.asyncio
    async def test_operational_telemetry_can_be_shed(self) -> None:
        """Test that operational telemetry CAN be shed under load (AC5)."""
        service = LoadSheddingService()

        # Set high load
        await service.update_load(95.0)

        # Operational telemetry should be shed
        decision = await service.make_shedding_decision(
            item_type="metric_telemetry",
            is_constitutional=False,
        )

        assert decision.was_shed is True

    @pytest.mark.asyncio
    async def test_no_shedding_at_normal_load(self) -> None:
        """Test that no shedding occurs at normal load (AC5)."""
        service = LoadSheddingService()

        # Set normal load
        await service.update_load(50.0)

        # Nothing should be shed
        decision = await service.make_shedding_decision(
            item_type="metric_telemetry",
            is_constitutional=False,
        )

        assert decision.was_shed is False

    @pytest.mark.asyncio
    async def test_shedding_stats_tracked(self) -> None:
        """Test that shedding statistics are tracked (AC5)."""
        service = LoadSheddingService()

        await service.update_load(95.0)

        # Make some decisions
        await service.make_shedding_decision("telemetry", is_constitutional=False)
        await service.make_shedding_decision("breach", is_constitutional=True)

        stats = await service.get_shedding_stats()

        assert stats["total_decisions"] == 2
        assert stats["constitutional_protected"] == 1
        assert stats["telemetry_shed"] == 1

    @pytest.mark.asyncio
    async def test_raises_on_attempted_constitutional_shedding(self) -> None:
        """Test that attempting to shed constitutional event raises error (FR107)."""
        service = LoadSheddingService()

        with pytest.raises(ConstitutionalEventSheddingError):
            await service.raise_if_shedding_constitutional(
                item_type="constitutional_event",
            )


class TestPatternViolationDetection:
    """Integration tests for AC6: Pattern violation detection from FMEA risk matrix."""

    def test_pv001_raw_string_event_type_detection(self) -> None:
        """Test that PV-001 raw string event type is detected (AC6)."""
        service = PatternViolationService()

        # Validate a raw string event type (invalid)
        is_valid = service.validate_event_type("raw_string_event")

        assert is_valid is False

        violations = service.detect_violations()
        assert len(violations) == 1
        assert violations[0].violation_type == PatternViolationType.RAW_STRING_EVENT_TYPE

    def test_pv002_plain_string_hash_detection(self) -> None:
        """Test that PV-002 plain string hash is detected (AC6)."""
        service = PatternViolationService()

        # Validate a plain string hash (invalid)
        is_valid = service.validate_content_ref("plain_hash_no_prefix")

        assert is_valid is False

        violations = service.detect_violations()
        assert len(violations) == 1
        assert violations[0].violation_type == PatternViolationType.PLAIN_STRING_HASH

    def test_pv003_missing_halt_guard_detection(self) -> None:
        """Test that PV-003 missing HaltGuard is detected (AC6)."""
        service = PatternViolationService()

        # Create a service without halt checker
        class ServiceWithoutHaltChecker:
            pass

        test_service = ServiceWithoutHaltChecker()
        is_valid = service.validate_halt_guard_injection(test_service)

        assert is_valid is False

        violations = service.detect_violations()
        assert len(violations) == 1
        assert violations[0].violation_type == PatternViolationType.MISSING_HALT_GUARD

    def test_valid_enum_event_type_passes(self) -> None:
        """Test that valid enum event types pass validation (AC6)."""
        from enum import Enum

        class ValidEventType(Enum):
            TEST = "test"

        service = PatternViolationService()
        is_valid = service.validate_event_type(ValidEventType.TEST)

        assert is_valid is True

        violations = service.detect_violations()
        assert len(violations) == 0

    def test_violation_blocking_decision(self) -> None:
        """Test that blocking violations prevent deployment (AC6)."""
        service = PatternViolationService()

        # Create a blocking violation
        service.validate_content_ref("plain_hash")  # PV-002 is critical

        blocking = service.get_blocking_violations()
        assert len(blocking) >= 1
        assert blocking[0].blocks_deployment is True


class TestHaltCheckIntegration:
    """Integration tests for CT-11: HALT CHECK FIRST."""

    @pytest.mark.asyncio
    async def test_metric_recording_blocked_when_halted(self) -> None:
        """Test that metric recording is blocked when system halted (CT-11)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=True, halt_reason="Test halt")
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        # Add a threshold
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test",
            warning_value=3.0,
            critical_value=10.0,
        )
        registry.add_threshold(threshold)

        with pytest.raises(SystemHaltedError):
            await service.record_metric(FailureModeId.VAL_1, "test", 5.0)

    @pytest.mark.asyncio
    async def test_threshold_configuration_blocked_when_halted(self) -> None:
        """Test that threshold configuration is blocked when halted (CT-11)."""
        registry = FailureModeRegistryStub()
        halt_checker = HaltCheckerStub(force_halted=True, halt_reason="Test halt")
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        with pytest.raises(SystemHaltedError):
            await service.configure_threshold(
                mode_id=FailureModeId.VAL_1,
                metric_name="test",
                warning_value=3.0,
                critical_value=10.0,
            )

    @pytest.mark.asyncio
    async def test_reads_allowed_when_halted(self) -> None:
        """Test that read operations are allowed when halted (CT-11)."""
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=True, halt_reason="Test halt")
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        # These should not raise
        modes = await service.get_all_failure_modes()
        assert len(modes) == len(DEFAULT_FAILURE_MODES)

        summary = await service.get_health_summary()
        assert summary is not None


class TestEndToEndFlow:
    """End-to-end integration tests for the complete failure prevention flow."""

    @pytest.mark.asyncio
    async def test_full_failure_mode_lifecycle(self) -> None:
        """Test complete failure mode monitoring lifecycle."""
        # Setup
        registry = FailureModeRegistryStub()
        registry.pre_populate_default_modes()
        halt_checker = HaltCheckerStub(force_halted=False)
        service = FailurePreventionService(registry=registry, halt_checker=halt_checker)

        # 1. Configure threshold
        await service.configure_threshold(
            mode_id=FailureModeId.VAL_1,
            metric_name="signature_failures",
            warning_value=3.0,
            critical_value=10.0,
        )

        # 2. Check initial healthy status
        status = await service.check_failure_mode(FailureModeId.VAL_1)
        assert status == FailureModeStatus.HEALTHY

        # 3. Record metric at warning level
        status = await service.record_metric(
            FailureModeId.VAL_1,
            "signature_failures",
            5.0,
        )
        assert status == FailureModeStatus.WARNING

        # 4. Verify warning generated
        warnings = await service.get_early_warnings()
        assert len(warnings) >= 1

        # 5. Check health summary reflects warning
        summary = await service.get_health_summary()
        assert summary.warning_count >= 1

        # 6. Acknowledge warning
        warning = warnings[0]
        await service.acknowledge_warning(str(warning.warning_id), "operator")

    @pytest.mark.asyncio
    async def test_full_query_monitoring_flow(self) -> None:
        """Test complete query performance monitoring flow."""
        service = QueryPerformanceService()

        # 1. Start multiple queries
        q1 = await service.start_query(event_count=1000)
        q2 = await service.start_query(event_count=5000)
        q3 = await service.start_query(event_count=15000)  # Large, batched

        # 2. Track completion
        await service.track_query(q1, event_count=1000, duration_ms=1000.0)
        await service.track_query(q2, event_count=5000, duration_ms=35000.0)  # SLA violation

        # 3. Update batch progress for large query
        await service.update_batch_progress(q3, processed_events=5000)
        progress = await service.get_batch_progress(q3)
        assert progress is not None
        assert progress.processed_events == 5000

        # 4. Complete large query
        await service.track_query(q3, event_count=15000, duration_ms=45000.0)

        # 5. Check stats
        stats = await service.get_compliance_stats()
        assert stats["total_queries"] == 3
        assert stats["non_compliant_count"] == 1  # q2 violated SLA

    @pytest.mark.asyncio
    async def test_full_load_shedding_flow(self) -> None:
        """Test complete load shedding decision flow."""
        service = LoadSheddingService()

        # 1. Start at normal load - no shedding
        await service.update_load(50.0)
        d1 = await service.make_shedding_decision("metric1", is_constitutional=False)
        assert d1.was_shed is False

        # 2. Increase to high load - operational shed
        await service.update_load(95.0)
        d2 = await service.make_shedding_decision("metric2", is_constitutional=False)
        assert d2.was_shed is True

        # 3. Constitutional still protected
        d3 = await service.make_shedding_decision("breach", is_constitutional=True)
        assert d3.was_shed is False

        # 4. Check stats
        stats = await service.get_shedding_stats()
        assert stats["total_decisions"] == 3
        assert stats["telemetry_shed"] == 1
        assert stats["constitutional_protected"] == 1

        # 5. Get recent decisions
        decisions = await service.get_recent_decisions()
        assert len(decisions) == 3
