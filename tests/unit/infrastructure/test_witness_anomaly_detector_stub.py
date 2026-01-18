"""Unit tests for witness anomaly detector stub (Story 6.6, FR116)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.witness_anomaly_detector import WitnessAnomalyResult
from src.domain.events.witness_anomaly import WitnessAnomalyType
from src.infrastructure.stubs.witness_anomaly_detector_stub import (
    WitnessAnomalyDetectorStub,
)


class TestWitnessAnomalyDetectorStubInit:
    """Tests for WitnessAnomalyDetectorStub initialization."""

    def test_initializes_empty(self) -> None:
        """Test stub initializes with empty state."""
        stub = WitnessAnomalyDetectorStub()

        assert stub._co_occurrence_anomalies == []
        assert stub._unavailability_anomalies == []
        assert stub._excluded_pairs == {}


class TestAnalyzeCoOccurrence:
    """Tests for analyze_co_occurrence method."""

    @pytest.mark.asyncio
    async def test_returns_empty_by_default(self) -> None:
        """Test returns empty list by default."""
        stub = WitnessAnomalyDetectorStub()

        results = await stub.analyze_co_occurrence(window_hours=168)

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_injected_anomalies(self) -> None:
        """Test returns injected co-occurrence anomalies."""
        stub = WitnessAnomalyDetectorStub()
        anomaly = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.85,
            affected_witnesses=("witness1", "witness2"),
            occurrence_count=15,
            expected_count=5.0,
            details="Test anomaly",
        )
        stub.inject_anomaly(anomaly)

        results = await stub.analyze_co_occurrence(window_hours=168)

        assert len(results) == 1
        assert results[0] == anomaly

    @pytest.mark.asyncio
    async def test_uses_set_anomalies(self) -> None:
        """Test returns anomalies set via set_co_occurrence_anomalies."""
        stub = WitnessAnomalyDetectorStub()
        anomalies = [
            WitnessAnomalyResult(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                confidence_score=0.8,
                affected_witnesses=("w1", "w2"),
                occurrence_count=10,
                expected_count=5.0,
                details="Test 1",
            ),
            WitnessAnomalyResult(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                confidence_score=0.9,
                affected_witnesses=("w3", "w4"),
                occurrence_count=20,
                expected_count=5.0,
                details="Test 2",
            ),
        ]
        stub.set_co_occurrence_anomalies(anomalies)

        results = await stub.analyze_co_occurrence(window_hours=168)

        assert len(results) == 2


class TestAnalyzeUnavailabilityPatterns:
    """Tests for analyze_unavailability_patterns method."""

    @pytest.mark.asyncio
    async def test_returns_empty_by_default(self) -> None:
        """Test returns empty list by default."""
        stub = WitnessAnomalyDetectorStub()

        results = await stub.analyze_unavailability_patterns(window_hours=168)

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_injected_anomalies(self) -> None:
        """Test returns injected unavailability anomalies."""
        stub = WitnessAnomalyDetectorStub()
        anomaly = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.UNAVAILABILITY_PATTERN,
            confidence_score=0.75,
            affected_witnesses=("witness1",),
            occurrence_count=10,
            expected_count=2.0,
            details="Unavailability pattern",
        )
        stub.inject_anomaly(anomaly)

        results = await stub.analyze_unavailability_patterns(window_hours=168)

        assert len(results) == 1
        assert results[0] == anomaly

    @pytest.mark.asyncio
    async def test_routes_by_anomaly_type(self) -> None:
        """Test inject_anomaly routes to correct list by type."""
        stub = WitnessAnomalyDetectorStub()

        co_occurrence = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.8,
            affected_witnesses=("w1", "w2"),
            occurrence_count=10,
            expected_count=5.0,
            details="Co-occurrence",
        )
        unavailability = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.UNAVAILABILITY_PATTERN,
            confidence_score=0.75,
            affected_witnesses=("w3",),
            occurrence_count=8,
            expected_count=2.0,
            details="Unavailability",
        )

        stub.inject_anomaly(co_occurrence)
        stub.inject_anomaly(unavailability)

        co_results = await stub.analyze_co_occurrence(168)
        unavail_results = await stub.analyze_unavailability_patterns(168)

        assert len(co_results) == 1
        assert co_results[0].anomaly_type == WitnessAnomalyType.CO_OCCURRENCE
        assert len(unavail_results) == 1
        assert (
            unavail_results[0].anomaly_type == WitnessAnomalyType.UNAVAILABILITY_PATTERN
        )


class TestExcludePair:
    """Tests for exclude_pair method."""

    @pytest.mark.asyncio
    async def test_excludes_pair(self) -> None:
        """Test excludes a pair."""
        stub = WitnessAnomalyDetectorStub()

        await stub.exclude_pair(
            pair_key="witness1:witness2",
            duration_hours=24,
            reason="Test exclusion",
            confidence=0.85,
        )

        assert "witness1:witness2" in stub._excluded_pairs
        exclusion = stub._excluded_pairs["witness1:witness2"]
        assert exclusion.pair_key == "witness1:witness2"
        assert exclusion.reason == "Test exclusion"
        assert exclusion.confidence == 0.85

    @pytest.mark.asyncio
    async def test_sets_exclusion_duration(self) -> None:
        """Test sets correct exclusion duration."""
        stub = WitnessAnomalyDetectorStub()
        before = datetime.now(timezone.utc)

        await stub.exclude_pair(
            pair_key="witness1:witness2",
            duration_hours=48,
            reason="Test",
            confidence=0.8,
        )

        after = datetime.now(timezone.utc)
        exclusion = stub._excluded_pairs["witness1:witness2"]

        # Verify excluded_until is approximately 48 hours from now
        expected_min = before + timedelta(hours=48)
        expected_max = after + timedelta(hours=48)
        assert expected_min <= exclusion.excluded_until <= expected_max


class TestClearPairExclusion:
    """Tests for clear_pair_exclusion method."""

    @pytest.mark.asyncio
    async def test_clears_existing_exclusion(self) -> None:
        """Test clears an existing exclusion."""
        stub = WitnessAnomalyDetectorStub()
        await stub.exclude_pair("witness1:witness2", 24, "Test", 0.8)

        result = await stub.clear_pair_exclusion("witness1:witness2")

        assert result is True
        assert "witness1:witness2" not in stub._excluded_pairs

    @pytest.mark.asyncio
    async def test_returns_false_for_non_excluded(self) -> None:
        """Test returns False for non-excluded pair."""
        stub = WitnessAnomalyDetectorStub()

        result = await stub.clear_pair_exclusion("witness1:witness2")

        assert result is False


class TestIsPairExcluded:
    """Tests for is_pair_excluded method."""

    @pytest.mark.asyncio
    async def test_returns_true_for_excluded(self) -> None:
        """Test returns True for excluded pair."""
        stub = WitnessAnomalyDetectorStub()
        await stub.exclude_pair("witness1:witness2", 24, "Test", 0.8)

        result = await stub.is_pair_excluded("witness1:witness2")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_non_excluded(self) -> None:
        """Test returns False for non-excluded pair."""
        stub = WitnessAnomalyDetectorStub()

        result = await stub.is_pair_excluded("witness1:witness2")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_expired_exclusion(self) -> None:
        """Test returns False for expired exclusion."""
        stub = WitnessAnomalyDetectorStub()

        # Manually create expired exclusion
        from src.application.ports.witness_anomaly_detector import PairExclusion

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        stub._excluded_pairs["witness1:witness2"] = PairExclusion(
            pair_key="witness1:witness2",
            excluded_at=past - timedelta(hours=24),
            excluded_until=past,  # Already expired
            reason="Test",
            confidence=0.8,
        )

        result = await stub.is_pair_excluded("witness1:witness2")

        assert result is False
        # Should have been pruned
        assert "witness1:witness2" not in stub._excluded_pairs


class TestGetExclusionDetails:
    """Tests for get_exclusion_details method."""

    @pytest.mark.asyncio
    async def test_returns_exclusion_details(self) -> None:
        """Test returns exclusion details for excluded pair."""
        stub = WitnessAnomalyDetectorStub()
        await stub.exclude_pair("witness1:witness2", 24, "Test reason", 0.85)

        result = await stub.get_exclusion_details("witness1:witness2")

        assert result is not None
        assert result.pair_key == "witness1:witness2"
        assert result.reason == "Test reason"
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_returns_none_for_non_excluded(self) -> None:
        """Test returns None for non-excluded pair."""
        stub = WitnessAnomalyDetectorStub()

        result = await stub.get_exclusion_details("witness1:witness2")

        assert result is None


class TestGetExcludedPairs:
    """Tests for get_excluded_pairs method."""

    @pytest.mark.asyncio
    async def test_returns_empty_by_default(self) -> None:
        """Test returns empty set by default."""
        stub = WitnessAnomalyDetectorStub()

        result = await stub.get_excluded_pairs()

        assert result == set()

    @pytest.mark.asyncio
    async def test_returns_all_excluded_pairs(self) -> None:
        """Test returns all excluded pair keys."""
        stub = WitnessAnomalyDetectorStub()
        await stub.exclude_pair("witness1:witness2", 24, "Test 1", 0.8)
        await stub.exclude_pair("witness3:witness4", 24, "Test 2", 0.85)

        result = await stub.get_excluded_pairs()

        assert result == {"witness1:witness2", "witness3:witness4"}


class TestClear:
    """Tests for clear method."""

    @pytest.mark.asyncio
    async def test_clears_all_state(self) -> None:
        """Test clears all state."""
        stub = WitnessAnomalyDetectorStub()

        # Add some state
        anomaly = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.8,
            affected_witnesses=("w1", "w2"),
            occurrence_count=10,
            expected_count=5.0,
            details="Test",
        )
        stub.inject_anomaly(anomaly)
        await stub.exclude_pair("witness1:witness2", 24, "Test", 0.8)

        stub.clear()

        assert stub._co_occurrence_anomalies == []
        assert stub._unavailability_anomalies == []
        assert stub._excluded_pairs == {}


class TestExpirationPruning:
    """Tests for automatic exclusion expiration pruning."""

    @pytest.mark.asyncio
    async def test_prunes_on_analyze_co_occurrence(self) -> None:
        """Test expired exclusions are pruned during analyze_co_occurrence."""
        stub = WitnessAnomalyDetectorStub()

        # Manually create expired exclusion
        from src.application.ports.witness_anomaly_detector import PairExclusion

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        stub._excluded_pairs["witness1:witness2"] = PairExclusion(
            pair_key="witness1:witness2",
            excluded_at=past - timedelta(hours=24),
            excluded_until=past,
            reason="Test",
            confidence=0.8,
        )

        await stub.analyze_co_occurrence(168)

        assert "witness1:witness2" not in stub._excluded_pairs

    @pytest.mark.asyncio
    async def test_prunes_on_get_excluded_pairs(self) -> None:
        """Test expired exclusions are pruned during get_excluded_pairs."""
        stub = WitnessAnomalyDetectorStub()

        # Manually create one expired and one active exclusion
        from src.application.ports.witness_anomaly_detector import PairExclusion

        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=24)

        stub._excluded_pairs["expired:pair"] = PairExclusion(
            pair_key="expired:pair",
            excluded_at=past - timedelta(hours=24),
            excluded_until=past,
            reason="Expired",
            confidence=0.8,
        )
        stub._excluded_pairs["active:pair"] = PairExclusion(
            pair_key="active:pair",
            excluded_at=now,
            excluded_until=future,
            reason="Active",
            confidence=0.9,
        )

        result = await stub.get_excluded_pairs()

        assert result == {"active:pair"}
        assert "expired:pair" not in stub._excluded_pairs
