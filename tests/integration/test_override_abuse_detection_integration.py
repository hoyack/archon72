"""Integration tests for Override Abuse Detection Service (Story 5.9).

Tests end-to-end flows for:
- AC1: FR86 - Constitutional constraint validation
- AC2: FR87 - History edit and evidence destruction rejection
- AC3: FP-3 - Statistical pattern detection
- AC4: ADR-7 - Aggregate anomaly detection ceremony support

Constitutional Constraints:
- FR86: System SHALL validate override commands against constitutional constraints
- FR87: Override commands violating constraints SHALL be rejected and logged
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events MUST be witnessed
- FP-3: Patient attacker detection needs ADR-7
"""

import contextlib
from unittest.mock import AsyncMock

import pytest

from src.application.ports.anomaly_detector import AnomalyResult, FrequencyData
from src.application.services.override_abuse_detection_service import (
    ABUSE_DETECTION_SYSTEM_AGENT_ID,
    OverrideAbuseDetectionService,
)
from src.domain.errors.override_abuse import (
    ConstitutionalConstraintViolationError,
    EvidenceDestructionAttemptError,
    HistoryEditAttemptError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.override_abuse import (
    ANOMALY_DETECTED_EVENT_TYPE,
    OVERRIDE_ABUSE_REJECTED_EVENT_TYPE,
    AnomalyType,
    ViolationType,
)
from src.infrastructure.stubs.anomaly_detector_stub import AnomalyDetectorStub
from src.infrastructure.stubs.override_abuse_validator_stub import (
    OverrideAbuseValidatorStub,
)


class TestAC1ConstitutionalConstraintValidation:
    """AC1: FR86 - Constitutional constraint validation.

    validate_override_command calls OverrideAbuseValidatorProtocol and writes
    witnessed OverrideAbuseRejectedEvent for any constitutional violation.
    """

    @pytest.fixture
    def service_with_mocks(
        self,
    ) -> tuple[
        OverrideAbuseDetectionService,
        OverrideAbuseValidatorStub,
        AnomalyDetectorStub,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        abuse_validator = OverrideAbuseValidatorStub()
        anomaly_detector = AnomalyDetectorStub()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)
        mock_halt_checker.get_halt_reason = AsyncMock(return_value=None)

        service = OverrideAbuseDetectionService(
            abuse_validator=abuse_validator,
            anomaly_detector=anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
        )

        return service, abuse_validator, anomaly_detector, mock_event_writer

    @pytest.mark.asyncio
    async def test_valid_override_passes_constitutional_check(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            OverrideAbuseValidatorStub,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Valid override command should pass validation (FR86)."""
        service, _, _, mock_event_writer = service_with_mocks

        result = await service.validate_override_command(
            scope="voting.extension",
            action_type="extend",
            keeper_id="KEEPER:alice",
        )

        assert result.is_valid is True
        # No abuse event should be written for valid override
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_forbidden_scope_rejected_with_event(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            OverrideAbuseValidatorStub,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Forbidden scope should be rejected and logged (FR86)."""
        service, abuse_validator, _, mock_event_writer = service_with_mocks

        # Add custom forbidden scope
        abuse_validator.add_forbidden_scope("test.forbidden.scope")

        with pytest.raises(ConstitutionalConstraintViolationError):
            await service.validate_override_command(
                scope="test.forbidden.scope",
                action_type="execute",
                keeper_id="KEEPER:bob",
            )

        # Verify abuse rejection event was written with witnessing
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == OVERRIDE_ABUSE_REJECTED_EVENT_TYPE
        assert call_kwargs["agent_id"] == ABUSE_DETECTION_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_halted_system_rejects_validation(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            OverrideAbuseValidatorStub,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Validation should fail when system is halted (CT-11)."""
        service, _, _, mock_event_writer = service_with_mocks

        # Set system to halted state
        service._halt_checker.is_halted = AsyncMock(return_value=True)
        service._halt_checker.get_halt_reason = AsyncMock(return_value="Test halt")

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.validate_override_command(
                scope="safe.scope",
                action_type="execute",
                keeper_id="KEEPER:charlie",
            )

        assert "CT-11" in str(exc_info.value)


class TestAC2HistoryEditAndEvidenceDestruction:
    """AC2: FR87 - History edit and evidence destruction rejection.

    History edit and evidence destruction attempts SHALL be rejected
    with HistoryEditAttemptError / EvidenceDestructionAttemptError
    and witnessed OverrideAbuseRejectedEvent.
    """

    @pytest.fixture
    def service_with_mocks(
        self,
    ) -> tuple[
        OverrideAbuseDetectionService,
        OverrideAbuseValidatorStub,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        abuse_validator = OverrideAbuseValidatorStub()
        anomaly_detector = AnomalyDetectorStub()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)

        service = OverrideAbuseDetectionService(
            abuse_validator=abuse_validator,
            anomaly_detector=anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
        )

        return service, abuse_validator, mock_event_writer

    @pytest.mark.asyncio
    async def test_history_edit_attempt_raises_specific_error(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            OverrideAbuseValidatorStub,
            AsyncMock,
        ],
    ) -> None:
        """History edit attempt should raise HistoryEditAttemptError (FR87)."""
        service, _, _ = service_with_mocks

        with pytest.raises(HistoryEditAttemptError) as exc_info:
            await service.validate_override_command(
                scope="event_store.delete",
                action_type="execute",
                keeper_id="KEEPER:attacker",
            )

        assert "event_store.delete" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_history_edit_writes_rejection_event(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            OverrideAbuseValidatorStub,
            AsyncMock,
        ],
    ) -> None:
        """History edit should write witnessed rejection event (FR87, CT-12)."""
        service, _, mock_event_writer = service_with_mocks

        with pytest.raises(HistoryEditAttemptError):
            await service.validate_override_command(
                scope="history",
                action_type="delete",
                keeper_id="KEEPER:attacker",
            )

        # Verify event was written
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs

        assert call_kwargs["event_type"] == OVERRIDE_ABUSE_REJECTED_EVENT_TYPE
        payload = call_kwargs["payload"]
        assert payload["violation_type"] == ViolationType.HISTORY_EDIT.value
        assert payload["keeper_id"] == "KEEPER:attacker"
        assert "FR87" in payload["violation_details"]

    @pytest.mark.asyncio
    async def test_evidence_destruction_raises_specific_error(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            OverrideAbuseValidatorStub,
            AsyncMock,
        ],
    ) -> None:
        """Evidence destruction should raise EvidenceDestructionAttemptError (FR87)."""
        service, _, _ = service_with_mocks

        with pytest.raises(EvidenceDestructionAttemptError) as exc_info:
            await service.validate_override_command(
                scope="witness.remove",
                action_type="execute",
                keeper_id="KEEPER:attacker",
            )

        assert "witness.remove" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_evidence_destruction_writes_rejection_event(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            OverrideAbuseValidatorStub,
            AsyncMock,
        ],
    ) -> None:
        """Evidence destruction should write witnessed rejection event (FR87, CT-12)."""
        service, _, mock_event_writer = service_with_mocks

        with pytest.raises(EvidenceDestructionAttemptError):
            await service.validate_override_command(
                scope="signature.invalidate",
                action_type="execute",
                keeper_id="KEEPER:evil",
            )

        # Verify event was written
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs

        assert call_kwargs["event_type"] == OVERRIDE_ABUSE_REJECTED_EVENT_TYPE
        payload = call_kwargs["payload"]
        assert payload["violation_type"] == ViolationType.EVIDENCE_DESTRUCTION.value
        assert payload["keeper_id"] == "KEEPER:evil"


class TestAC3StatisticalPatternDetection:
    """AC3: FP-3 - Statistical pattern detection.

    detect_anomalies runs frequency spike and slow-burn erosion detection,
    returns anomalies with confidence >= 0.7, and writes witnessed events.
    """

    @pytest.fixture
    def service_with_mocks(
        self,
    ) -> tuple[
        OverrideAbuseDetectionService,
        AnomalyDetectorStub,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        abuse_validator = OverrideAbuseValidatorStub()
        anomaly_detector = AnomalyDetectorStub()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)

        service = OverrideAbuseDetectionService(
            abuse_validator=abuse_validator,
            anomaly_detector=anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
        )

        return service, anomaly_detector, mock_event_writer

    @pytest.mark.asyncio
    async def test_no_anomalies_returns_empty_list(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """No anomalies should return empty list."""
        service, _, mock_event_writer = service_with_mocks

        results = await service.detect_anomalies()

        assert results == []
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_frequency_spike_detected_and_logged(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Frequency spike should be detected and logged (FP-3)."""
        service, anomaly_detector, mock_event_writer = service_with_mocks

        # Inject frequency spike
        anomaly_detector.inject_frequency_spike(
            keeper_id="KEEPER:suspect",
            override_count=50,
            deviation=3.5,
            confidence=0.85,
        )

        results = await service.detect_anomalies()

        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.FREQUENCY_SPIKE
        assert results[0].confidence_score == 0.85

        # Verify event was written (CT-12 witnessing)
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == ANOMALY_DETECTED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_slow_burn_erosion_detected(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Slow-burn erosion should be detected (CT-9, FP-3)."""
        service, anomaly_detector, _ = service_with_mocks

        # Inject slow-burn erosion
        anomaly_detector.inject_slow_burn_erosion(
            keeper_ids=("KEEPER:patient_attacker",),
            confidence=0.75,
            growth_rate=0.15,
        )

        results = await service.detect_anomalies()

        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.SLOW_BURN_EROSION

    @pytest.mark.asyncio
    async def test_low_confidence_anomalies_filtered_out(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Anomalies below confidence threshold should be filtered (FP-3)."""
        service, anomaly_detector, mock_event_writer = service_with_mocks

        # Inject low-confidence anomaly
        low_confidence_anomaly = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.5,  # Below 0.7 threshold
            affected_keepers=("KEEPER:maybe",),
            details="Low confidence spike",
        )
        anomaly_detector.set_detected_anomalies([low_confidence_anomaly])

        results = await service.detect_anomalies()

        assert results == []  # Filtered out
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_detection_blocked_when_halted(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Anomaly detection should fail when system is halted (CT-11)."""
        service, _, _ = service_with_mocks

        service._halt_checker.is_halted = AsyncMock(return_value=True)
        service._halt_checker.get_halt_reason = AsyncMock(return_value="Fork detected")

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.detect_anomalies()

        assert "CT-11" in str(exc_info.value)


class TestAC4AggregateAnomalyDetectionCeremony:
    """AC4: ADR-7 - Aggregate anomaly detection ceremony support.

    run_weekly_anomaly_review generates AnomalyReviewReport with all
    anomalies for human review ceremony.
    """

    @pytest.fixture
    def service_with_mocks(
        self,
    ) -> tuple[
        OverrideAbuseDetectionService,
        AnomalyDetectorStub,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        abuse_validator = OverrideAbuseValidatorStub()
        anomaly_detector = AnomalyDetectorStub()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)

        service = OverrideAbuseDetectionService(
            abuse_validator=abuse_validator,
            anomaly_detector=anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
        )

        return service, anomaly_detector, mock_event_writer

    @pytest.mark.asyncio
    async def test_weekly_review_returns_comprehensive_report(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Weekly review should return comprehensive report (ADR-7)."""
        service, anomaly_detector, _ = service_with_mocks

        # Inject multiple anomalies
        anomaly_detector.inject_frequency_spike("KEEPER:1", 30, 2.5, 0.75)
        anomaly_detector.inject_frequency_spike("KEEPER:2", 60, 4.0, 0.92)
        anomaly_detector.inject_slow_burn_erosion(("KEEPER:3",), 0.8, 0.2)

        report = await service.run_weekly_anomaly_review()

        assert report.anomaly_count == 3
        # High confidence (>= 0.9): only 0.92
        # Medium confidence (0.7 <= x < 0.9): 0.75, 0.8
        assert report.high_confidence_count == 1
        assert report.medium_confidence_count == 2
        assert report.review_timestamp is not None

    @pytest.mark.asyncio
    async def test_weekly_review_blocked_when_halted(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Weekly review should fail when system is halted (CT-11)."""
        service, _, _ = service_with_mocks

        service._halt_checker.is_halted = AsyncMock(return_value=True)
        service._halt_checker.get_halt_reason = AsyncMock(return_value="Critical")

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.run_weekly_anomaly_review()

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_keeper_behavior_analysis(
        self,
        service_with_mocks: tuple[
            OverrideAbuseDetectionService,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Individual Keeper behavior analysis should work (ADR-7 support)."""
        service, anomaly_detector, _ = service_with_mocks

        # Set keeper frequency with high deviation (outlier)
        anomaly_detector.set_keeper_frequency(
            "KEEPER:outlier",
            FrequencyData(
                override_count=100,
                time_window_days=90,
                daily_rate=1.1,
                deviation_from_baseline=3.5,
            ),
        )

        report = await service.analyze_keeper_behavior("KEEPER:outlier")

        assert report.keeper_id == "KEEPER:outlier"
        assert report.is_outlier is True
        assert report.outlier_reason is not None
        assert "3.50" in report.outlier_reason  # Contains deviation value


class TestEndToEndFlow:
    """End-to-end integration tests for complete flows."""

    @pytest.fixture
    def full_service(
        self,
    ) -> tuple[
        OverrideAbuseDetectionService,
        OverrideAbuseValidatorStub,
        AnomalyDetectorStub,
        AsyncMock,
    ]:
        """Create full service with all components."""
        abuse_validator = OverrideAbuseValidatorStub()
        anomaly_detector = AnomalyDetectorStub()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)

        service = OverrideAbuseDetectionService(
            abuse_validator=abuse_validator,
            anomaly_detector=anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
        )

        return service, abuse_validator, anomaly_detector, mock_event_writer

    @pytest.mark.asyncio
    async def test_full_abuse_detection_workflow(
        self,
        full_service: tuple[
            OverrideAbuseDetectionService,
            OverrideAbuseValidatorStub,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Test complete abuse detection workflow.

        1. Validate safe override (passes)
        2. Validate forbidden override (fails, logged)
        3. Detect anomalies (finds and logs)
        4. Run weekly review
        """
        service, abuse_validator, anomaly_detector, mock_event_writer = full_service

        # Step 1: Safe override passes
        result = await service.validate_override_command(
            scope="user.preferences",
            action_type="update",
            keeper_id="KEEPER:good",
        )
        assert result.is_valid is True

        # Step 2: Forbidden override fails and is logged
        abuse_validator.add_forbidden_scope("restricted.area")
        with pytest.raises(ConstitutionalConstraintViolationError):
            await service.validate_override_command(
                scope="restricted.area",
                action_type="access",
                keeper_id="KEEPER:curious",
            )

        # Verify first event was written
        assert mock_event_writer.write_event.call_count == 1

        # Reset for next phase
        mock_event_writer.reset_mock()

        # Step 3: Detect anomalies
        anomaly_detector.inject_frequency_spike("KEEPER:suspicious", 40, 3.0, 0.8)
        anomalies = await service.detect_anomalies()
        assert len(anomalies) == 1

        # Verify anomaly event was written
        assert mock_event_writer.write_event.call_count == 1

        # Reset for next phase
        mock_event_writer.reset_mock()

        # Step 4: Weekly review
        report = await service.run_weekly_anomaly_review()
        assert report.anomaly_count >= 1

    @pytest.mark.asyncio
    async def test_multiple_violation_types_tracked_separately(
        self,
        full_service: tuple[
            OverrideAbuseDetectionService,
            OverrideAbuseValidatorStub,
            AnomalyDetectorStub,
            AsyncMock,
        ],
    ) -> None:
        """Each violation type should be tracked with correct type."""
        service, _, _, mock_event_writer = full_service

        # Test history edit
        with contextlib.suppress(HistoryEditAttemptError):
            await service.validate_override_command(
                scope="history",
                action_type="delete",
                keeper_id="KEEPER:1",
            )

        # Test evidence destruction
        with contextlib.suppress(EvidenceDestructionAttemptError):
            await service.validate_override_command(
                scope="evidence.delete",
                action_type="execute",
                keeper_id="KEEPER:2",
            )

        # Verify both events have correct violation types
        assert mock_event_writer.write_event.call_count == 2
        calls = mock_event_writer.write_event.call_args_list

        violation_types = [call.kwargs["payload"]["violation_type"] for call in calls]
        assert ViolationType.HISTORY_EDIT.value in violation_types
        assert ViolationType.EVIDENCE_DESTRUCTION.value in violation_types
