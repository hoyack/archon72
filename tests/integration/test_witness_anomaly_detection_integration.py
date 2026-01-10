"""Integration tests for witness anomaly detection (Story 6.6, FR116-FR117).

Tests the integration between:
- WitnessAnomalyDetectionService (FR116)
- WitnessPoolMonitoringService (FR117)
- VerifiableWitnessSelectionService (FR59-FR61)
- Infrastructure stubs

Constitutional Constraints verified:
- FR116: Witness unavailability pattern detection triggers security review
- FR117: Pool <12 blocks high-stakes, allows low-stakes, surfaces degraded mode
- CT-11: HALT CHECK FIRST at every operation
- CT-12: Witnessing creates accountability (anomaly events must be witnessable)
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.witness_anomaly_detector import WitnessAnomalyResult
from src.application.services.witness_anomaly_detection_service import (
    CONFIDENCE_THRESHOLD,
    WitnessAnomalyDetectionService,
)
from src.application.services.witness_pool_monitoring_service import (
    WitnessPoolMonitoringService,
)
from src.application.services.verifiable_witness_selection_service import (
    VerifiableWitnessSelectionService,
)
from src.domain.errors.witness_anomaly import (
    WitnessPoolDegradedError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.witness_anomaly import (
    ReviewStatus,
    WitnessAnomalyType,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.witness_anomaly_detector_stub import (
    WitnessAnomalyDetectorStub,
)
from src.infrastructure.stubs.witness_pool_monitor_stub import WitnessPoolMonitorStub
from src.infrastructure.stubs.entropy_source_stub import SecureEntropySourceStub
from src.infrastructure.stubs.witness_pair_history_stub import InMemoryWitnessPairHistory
from src.infrastructure.stubs.event_store_stub import EventStoreStub


class TestFR116WitnessAnomalyDetection:
    """Integration tests for FR116: Witness unavailability pattern detection."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create halt checker stub."""
        stub = HaltCheckerStub()
        stub.set_halted(False)
        return stub

    @pytest.fixture
    def anomaly_detector(self) -> WitnessAnomalyDetectorStub:
        """Create anomaly detector stub."""
        return WitnessAnomalyDetectorStub()

    @pytest.fixture
    def detection_service(
        self, halt_checker: HaltCheckerStub, anomaly_detector: WitnessAnomalyDetectorStub
    ) -> WitnessAnomalyDetectionService:
        """Create anomaly detection service."""
        return WitnessAnomalyDetectionService(
            halt_checker=halt_checker,
            anomaly_detector=anomaly_detector,
        )

    @pytest.mark.asyncio
    async def test_detects_co_occurrence_anomaly(
        self,
        detection_service: WitnessAnomalyDetectionService,
        anomaly_detector: WitnessAnomalyDetectorStub,
    ) -> None:
        """Test FR116: Detects suspicious witness co-occurrence patterns."""
        # Inject high-confidence anomaly
        anomaly = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.85,  # Above threshold
            affected_witnesses=("WITNESS:001", "WITNESS:002"),
            occurrence_count=25,
            expected_count=5.0,
            details="Pair appears together 5x more often than expected",
        )
        anomaly_detector.inject_anomaly(anomaly)

        results = await detection_service.run_anomaly_scan(window_hours=168)

        assert len(results) == 1
        assert results[0].anomaly_type == WitnessAnomalyType.CO_OCCURRENCE
        assert results[0].affected_witnesses == ("WITNESS:001", "WITNESS:002")
        assert results[0].review_status == ReviewStatus.PENDING

    @pytest.mark.asyncio
    async def test_detects_unavailability_pattern(
        self,
        detection_service: WitnessAnomalyDetectionService,
        anomaly_detector: WitnessAnomalyDetectorStub,
    ) -> None:
        """Test FR116: Detects repeated unavailability of same witnesses."""
        anomaly = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.UNAVAILABILITY_PATTERN,
            confidence_score=0.78,
            affected_witnesses=("WITNESS:003", "WITNESS:004", "WITNESS:005"),
            occurrence_count=12,
            expected_count=2.0,
            details="Pattern of coordinated unavailability detected",
        )
        anomaly_detector.inject_anomaly(anomaly)

        results = await detection_service.run_anomaly_scan(window_hours=168)

        assert len(results) == 1
        assert results[0].anomaly_type == WitnessAnomalyType.UNAVAILABILITY_PATTERN

    @pytest.mark.asyncio
    async def test_filters_low_confidence_anomalies(
        self,
        detection_service: WitnessAnomalyDetectionService,
        anomaly_detector: WitnessAnomalyDetectorStub,
    ) -> None:
        """Test FR116: Filters out low-confidence anomalies."""
        low_conf = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.5,  # Below threshold
            affected_witnesses=("W1", "W2"),
            occurrence_count=8,
            expected_count=5.0,
            details="Low confidence",
        )
        high_conf = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.9,
            affected_witnesses=("W3", "W4"),
            occurrence_count=25,
            expected_count=5.0,
            details="High confidence",
        )
        anomaly_detector.set_co_occurrence_anomalies([low_conf, high_conf])

        results = await detection_service.run_anomaly_scan()

        assert len(results) == 1
        assert results[0].confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_pair_exclusion_workflow(
        self,
        detection_service: WitnessAnomalyDetectionService,
        anomaly_detector: WitnessAnomalyDetectorStub,
    ) -> None:
        """Test FR116: Suspicious pair can be excluded and later cleared."""
        # Use simple pair format without colons in IDs
        pair_key = "witness1:witness2"

        # Initially not excluded
        is_excluded = await detection_service.check_pair_for_anomaly(pair_key)
        assert is_excluded is False

        # Exclude the pair
        payload = await detection_service.exclude_suspicious_pair(
            pair_key=pair_key,
            confidence=0.85,
            reason="Suspected collusion",
        )
        assert payload.affected_witnesses == ("witness1", "witness2")

        # Now excluded
        is_excluded = await detection_service.check_pair_for_anomaly(pair_key)
        assert is_excluded is True

        # Get exclusion details
        details = await detection_service.get_exclusion_details(pair_key)
        assert details is not None
        assert details.confidence == 0.85

        # Clear exclusion after review
        cleared = await detection_service.clear_pair_exclusion(pair_key)
        assert cleared is True

        # No longer excluded
        is_excluded = await detection_service.check_pair_for_anomaly(pair_key)
        assert is_excluded is False


class TestFR117WitnessPoolMonitoring:
    """Integration tests for FR117: Witness pool degraded mode."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create halt checker stub."""
        stub = HaltCheckerStub()
        stub.set_halted(False)
        return stub

    @pytest.fixture
    def pool_monitor(self) -> WitnessPoolMonitorStub:
        """Create pool monitor stub."""
        return WitnessPoolMonitorStub(initial_pool_size=15)

    @pytest.fixture
    def anomaly_detector(self) -> WitnessAnomalyDetectorStub:
        """Create anomaly detector stub."""
        return WitnessAnomalyDetectorStub()

    @pytest.fixture
    def monitoring_service(
        self,
        halt_checker: HaltCheckerStub,
        pool_monitor: WitnessPoolMonitorStub,
        anomaly_detector: WitnessAnomalyDetectorStub,
    ) -> WitnessPoolMonitoringService:
        """Create pool monitoring service."""
        return WitnessPoolMonitoringService(
            halt_checker=halt_checker,
            witness_pool=pool_monitor,
            anomaly_detector=anomaly_detector,
        )

    @pytest.mark.asyncio
    async def test_healthy_pool_allows_all_operations(
        self,
        monitoring_service: WitnessPoolMonitoringService,
    ) -> None:
        """Test FR117: Healthy pool (>=12) allows all operations."""
        status = await monitoring_service.check_pool_health()

        assert status.is_degraded is False
        assert status.available_count == 15

        can_high, _ = await monitoring_service.can_proceed_with_operation(high_stakes=True)
        can_low, _ = await monitoring_service.can_proceed_with_operation(high_stakes=False)

        assert can_high is True
        assert can_low is True

    @pytest.mark.asyncio
    async def test_degraded_pool_blocks_high_stakes(
        self,
        monitoring_service: WitnessPoolMonitoringService,
        pool_monitor: WitnessPoolMonitorStub,
    ) -> None:
        """Test FR117: Degraded pool (<12) blocks high-stakes operations."""
        pool_monitor.set_pool_size(8)

        status = await monitoring_service.check_pool_health()

        assert status.is_degraded is True
        assert status.available_count == 8

        can_high, reason = await monitoring_service.can_proceed_with_operation(high_stakes=True)

        assert can_high is False
        assert "FR117" in reason

    @pytest.mark.asyncio
    async def test_degraded_pool_allows_low_stakes(
        self,
        monitoring_service: WitnessPoolMonitoringService,
        pool_monitor: WitnessPoolMonitorStub,
    ) -> None:
        """Test FR117: Degraded pool allows low-stakes operations."""
        pool_monitor.set_pool_size(8)

        can_low, _ = await monitoring_service.can_proceed_with_operation(high_stakes=False)

        assert can_low is True

    @pytest.mark.asyncio
    async def test_surfaces_degraded_mode(
        self,
        monitoring_service: WitnessPoolMonitoringService,
        pool_monitor: WitnessPoolMonitorStub,
    ) -> None:
        """Test FR117: Degraded mode is publicly surfaced."""
        pool_monitor.set_pool_size(8)

        status = await monitoring_service.check_pool_health()
        payload = await monitoring_service.handle_pool_degraded(status)

        assert payload.available_witnesses == 8
        assert payload.minimum_required == 12
        assert payload.is_blocking is True
        assert payload.degraded_at is not None

    @pytest.mark.asyncio
    async def test_require_healthy_raises_for_degraded(
        self,
        monitoring_service: WitnessPoolMonitoringService,
        pool_monitor: WitnessPoolMonitorStub,
    ) -> None:
        """Test FR117: require_healthy_pool_for_high_stakes raises error."""
        pool_monitor.set_pool_size(8)

        with pytest.raises(WitnessPoolDegradedError) as exc_info:
            await monitoring_service.require_healthy_pool_for_high_stakes()

        assert exc_info.value.available == 8
        assert exc_info.value.minimum_required == 12
        assert "FR117" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tracks_degraded_duration(
        self,
        monitoring_service: WitnessPoolMonitoringService,
        pool_monitor: WitnessPoolMonitorStub,
    ) -> None:
        """Test FR117: Tracks when degraded mode started."""
        pool_monitor.set_pool_size(8)

        status1 = await monitoring_service.check_pool_health()
        degraded_time = status1.degraded_since

        assert degraded_time is not None

        # Second check should have same time
        status2 = await monitoring_service.check_pool_health()
        assert status2.degraded_since == degraded_time


class TestCT11HaltCheckFirst:
    """Integration tests for CT-11: HALT CHECK FIRST."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create halt checker stub."""
        return HaltCheckerStub()

    @pytest.fixture
    def anomaly_detector(self) -> WitnessAnomalyDetectorStub:
        """Create anomaly detector stub."""
        return WitnessAnomalyDetectorStub()

    @pytest.fixture
    def pool_monitor(self) -> WitnessPoolMonitorStub:
        """Create pool monitor stub."""
        return WitnessPoolMonitorStub()

    @pytest.mark.asyncio
    async def test_detection_service_halted(
        self,
        halt_checker: HaltCheckerStub,
        anomaly_detector: WitnessAnomalyDetectorStub,
    ) -> None:
        """Test CT-11: Detection service blocks when halted."""
        halt_checker.set_halted(True)
        service = WitnessAnomalyDetectionService(
            halt_checker=halt_checker,
            anomaly_detector=anomaly_detector,
        )

        with pytest.raises(SystemHaltedError):
            await service.run_anomaly_scan()

        with pytest.raises(SystemHaltedError):
            await service.check_pair_for_anomaly("test:pair")

        with pytest.raises(SystemHaltedError):
            await service.exclude_suspicious_pair("test:pair", 0.8)

    @pytest.mark.asyncio
    async def test_monitoring_service_halted(
        self,
        halt_checker: HaltCheckerStub,
        pool_monitor: WitnessPoolMonitorStub,
    ) -> None:
        """Test CT-11: Monitoring service blocks when halted."""
        halt_checker.set_halted(True)
        service = WitnessPoolMonitoringService(
            halt_checker=halt_checker,
            witness_pool=pool_monitor,
        )

        with pytest.raises(SystemHaltedError):
            await service.check_pool_health()

        with pytest.raises(SystemHaltedError):
            await service.is_degraded()

        with pytest.raises(SystemHaltedError):
            await service.can_proceed_with_operation(high_stakes=True)


class TestWitnessSelectionIntegration:
    """Integration tests for witness selection with anomaly detection."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create halt checker stub."""
        stub = HaltCheckerStub()
        stub.set_halted(False)
        return stub

    @pytest.fixture
    def entropy_source(self) -> SecureEntropySourceStub:
        """Create entropy source stub."""
        return SecureEntropySourceStub()

    @pytest.fixture
    def pair_history(self) -> InMemoryWitnessPairHistory:
        """Create pair history stub."""
        return InMemoryWitnessPairHistory()

    @pytest.fixture
    def anomaly_detector(self) -> WitnessAnomalyDetectorStub:
        """Create anomaly detector stub."""
        return WitnessAnomalyDetectorStub()

    @pytest.fixture
    def pool_stub(self) -> WitnessPoolMonitorStub:
        """Create witness pool stub that implements WitnessPoolProtocol."""
        return WitnessPoolMonitorStub(initial_pool_size=15)

    @pytest.fixture
    def event_store(self) -> EventStoreStub:
        """Create event store stub."""
        return EventStoreStub()

    @pytest.fixture
    def witness_pool(self) -> list[str]:
        """Create witness pool list."""
        return [f"WITNESS:{i:03d}" for i in range(15)]

    @pytest.mark.asyncio
    async def test_selection_excludes_anomalous_pairs(
        self,
        halt_checker: HaltCheckerStub,
        pool_stub: WitnessPoolMonitorStub,
        entropy_source: SecureEntropySourceStub,
        event_store: EventStoreStub,
        pair_history: InMemoryWitnessPairHistory,
        anomaly_detector: WitnessAnomalyDetectorStub,
        witness_pool: list[str],
    ) -> None:
        """Test witness selection respects anomaly exclusions."""
        service = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=pool_stub,
            entropy_source=entropy_source,
            event_store=event_store,
            pair_history=pair_history,
            anomaly_detector=anomaly_detector,
        )

        # Exclude a pair - use simple format
        await anomaly_detector.exclude_pair(
            "w0:w1",
            duration_hours=24,
            reason="Suspected anomaly",
            confidence=0.8,
        )

        # Test pair check directly
        is_excluded = await service.is_pair_excluded_by_anomaly("w0:w1")
        assert is_excluded is True

    @pytest.mark.asyncio
    async def test_selection_checks_pair_exclusion(
        self,
        halt_checker: HaltCheckerStub,
        pool_stub: WitnessPoolMonitorStub,
        entropy_source: SecureEntropySourceStub,
        event_store: EventStoreStub,
        pair_history: InMemoryWitnessPairHistory,
        anomaly_detector: WitnessAnomalyDetectorStub,
        witness_pool: list[str],
    ) -> None:
        """Test selection service uses anomaly detector for pair checks."""
        service = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=pool_stub,
            entropy_source=entropy_source,
            event_store=event_store,
            pair_history=pair_history,
            anomaly_detector=anomaly_detector,
        )

        # Initially no exclusions
        is_excluded = await service.is_pair_excluded_by_anomaly("w0:w1")
        assert is_excluded is False

        # Add exclusion
        await anomaly_detector.exclude_pair(
            "w0:w1",
            duration_hours=24,
            reason="Test",
            confidence=0.8,
        )

        # Now excluded
        is_excluded = await service.is_pair_excluded_by_anomaly("w0:w1")
        assert is_excluded is True


class TestAnomalyEventPayloadCreation:
    """Integration tests for anomaly event payload creation (CT-12)."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create halt checker stub."""
        stub = HaltCheckerStub()
        stub.set_halted(False)
        return stub

    @pytest.fixture
    def anomaly_detector(self) -> WitnessAnomalyDetectorStub:
        """Create anomaly detector stub."""
        return WitnessAnomalyDetectorStub()

    @pytest.fixture
    def detection_service(
        self, halt_checker: HaltCheckerStub, anomaly_detector: WitnessAnomalyDetectorStub
    ) -> WitnessAnomalyDetectionService:
        """Create anomaly detection service."""
        return WitnessAnomalyDetectionService(
            halt_checker=halt_checker,
            anomaly_detector=anomaly_detector,
        )

    @pytest.mark.asyncio
    async def test_exclusion_creates_witnessable_event(
        self,
        detection_service: WitnessAnomalyDetectionService,
    ) -> None:
        """Test CT-12: Exclusion creates event payload for witnessing."""
        payload = await detection_service.exclude_suspicious_pair(
            pair_key="WITNESS:001:WITNESS:002",
            confidence=0.85,
            duration_hours=24,
            reason="Suspected collusion based on co-occurrence analysis",
        )

        # Verify payload has all required fields for witnessing
        assert payload.anomaly_type == WitnessAnomalyType.CO_OCCURRENCE
        assert payload.affected_witnesses == ("WITNESS:001", "WITNESS:002")
        assert payload.confidence_score == 0.85
        assert payload.detected_at is not None
        assert payload.review_status == ReviewStatus.PENDING
        assert "collusion" in payload.details.lower()

    @pytest.mark.asyncio
    async def test_scan_creates_witnessable_events(
        self,
        detection_service: WitnessAnomalyDetectionService,
        anomaly_detector: WitnessAnomalyDetectorStub,
    ) -> None:
        """Test CT-12: Scan creates event payloads for witnessing."""
        anomaly = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.UNAVAILABILITY_PATTERN,
            confidence_score=0.8,
            affected_witnesses=("W1", "W2", "W3"),
            occurrence_count=15,
            expected_count=3.0,
            details="Coordinated unavailability",
        )
        anomaly_detector.inject_anomaly(anomaly)

        results = await detection_service.run_anomaly_scan()

        assert len(results) == 1
        payload = results[0]

        # Verify witnessable event fields
        assert payload.detection_window_hours == 168  # Default
        assert payload.occurrence_count == 15
        assert payload.expected_count == 3.0
        assert payload.review_status == ReviewStatus.PENDING


class TestEndToEndAnomalyWorkflow:
    """End-to-end integration tests for complete anomaly workflow."""

    @pytest.mark.asyncio
    async def test_complete_anomaly_detection_workflow(self) -> None:
        """Test complete workflow: detect -> exclude -> select -> clear."""
        # Setup
        halt_checker = HaltCheckerStub()
        halt_checker.set_halted(False)
        anomaly_detector = WitnessAnomalyDetectorStub()
        entropy_source = SecureEntropySourceStub()
        pair_history = InMemoryWitnessPairHistory()
        pool_stub = WitnessPoolMonitorStub(initial_pool_size=15)
        event_store = EventStoreStub()

        detection_service = WitnessAnomalyDetectionService(
            halt_checker=halt_checker,
            anomaly_detector=anomaly_detector,
        )
        selection_service = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=pool_stub,
            entropy_source=entropy_source,
            event_store=event_store,
            pair_history=pair_history,
            anomaly_detector=anomaly_detector,
        )

        # Step 1: Inject anomaly (simulating detection)
        anomaly = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.9,
            affected_witnesses=("w0", "w1"),
            occurrence_count=30,
            expected_count=5.0,
            details="High co-occurrence",
        )
        anomaly_detector.inject_anomaly(anomaly)

        # Step 2: Run scan
        results = await detection_service.run_anomaly_scan()
        assert len(results) == 1

        # Step 3: Exclude suspicious pair (use simple format)
        pair_key = "w0:w1"
        await detection_service.exclude_suspicious_pair(
            pair_key=pair_key,
            confidence=0.9,
            reason="Anomaly detected",
        )

        # Step 4: Verify exclusion affects selection
        excluded_pairs = await detection_service.get_all_excluded_pairs()
        assert pair_key in excluded_pairs

        is_excluded = await selection_service.is_pair_excluded_by_anomaly(pair_key)
        assert is_excluded is True

        # Step 5: Human review clears the pair
        cleared = await detection_service.clear_pair_exclusion(pair_key)
        assert cleared is True

        # Step 6: Verify pair is no longer excluded
        is_excluded = await selection_service.is_pair_excluded_by_anomaly(pair_key)
        assert is_excluded is False

    @pytest.mark.asyncio
    async def test_degraded_mode_workflow(self) -> None:
        """Test complete workflow: pool degrades -> surfaces -> restores."""
        # Setup
        halt_checker = HaltCheckerStub()
        halt_checker.set_halted(False)
        pool_monitor = WitnessPoolMonitorStub(initial_pool_size=15)

        monitoring_service = WitnessPoolMonitoringService(
            halt_checker=halt_checker,
            witness_pool=pool_monitor,
        )

        # Step 1: Verify healthy
        status = await monitoring_service.check_pool_health()
        assert status.is_degraded is False

        # Step 2: Pool degrades
        pool_monitor.set_pool_size(8)

        # Step 3: Check surfaces degraded mode
        status = await monitoring_service.check_pool_health()
        assert status.is_degraded is True
        assert status.degraded_since is not None

        # Step 4: High-stakes blocked
        can_proceed, reason = await monitoring_service.can_proceed_with_operation(high_stakes=True)
        assert can_proceed is False
        assert "FR117" in reason

        # Step 5: Low-stakes allowed
        can_proceed, _ = await monitoring_service.can_proceed_with_operation(high_stakes=False)
        assert can_proceed is True

        # Step 6: Create surfacing event
        payload = await monitoring_service.handle_pool_degraded(status)
        assert payload.is_blocking is True

        # Step 7: Pool restored
        pool_monitor.set_pool_size(15)

        # Step 8: Verify recovery
        status = await monitoring_service.check_pool_health()
        assert status.is_degraded is False
        assert status.degraded_since is None

        can_proceed, _ = await monitoring_service.can_proceed_with_operation(high_stakes=True)
        assert can_proceed is True
