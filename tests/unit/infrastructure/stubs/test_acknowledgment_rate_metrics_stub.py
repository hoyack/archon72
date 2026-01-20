"""Unit tests for AcknowledgmentRateMetricsStub (Story 3.6, FR-3.6)."""

from uuid import uuid4

import pytest

from src.infrastructure.stubs.acknowledgment_rate_metrics_stub import (
    AcknowledgmentRateMetricsStub,
)


class TestAcknowledgmentRateMetricsStub:
    """Tests for AcknowledgmentRateMetricsStub."""

    def test_record_participation_stores_metrics(self) -> None:
        """Test record_participation stores archon metrics."""
        stub = AcknowledgmentRateMetricsStub()
        archon_id = uuid4()

        stub.record_participation(archon_id)

        metrics = stub.get_metrics(archon_id)
        assert metrics is not None
        assert metrics.total_participations == 1

    def test_record_participation_tracks_calls(self) -> None:
        """Test participation calls are tracked."""
        stub = AcknowledgmentRateMetricsStub()
        archon_id = uuid4()

        stub.record_participation(archon_id)
        stub.record_participation(archon_id)

        assert len(stub.participation_calls) == 2
        assert stub.participation_calls[0] == archon_id
        assert stub.participation_calls[1] == archon_id

    def test_record_vote_acknowledge(self) -> None:
        """Test record_vote with ACKNOWLEDGE outcome."""
        stub = AcknowledgmentRateMetricsStub()
        archon_id = uuid4()

        # Must have participation before voting (domain constraint)
        stub.record_participation(archon_id)
        stub.record_vote(archon_id, "ACKNOWLEDGE")

        metrics = stub.get_metrics(archon_id)
        assert metrics is not None
        assert metrics.acknowledge_votes == 1

    def test_record_vote_refer(self) -> None:
        """Test record_vote with REFER outcome."""
        stub = AcknowledgmentRateMetricsStub()
        archon_id = uuid4()

        # Must have participation before voting (domain constraint)
        stub.record_participation(archon_id)
        stub.record_vote(archon_id, "REFER")

        metrics = stub.get_metrics(archon_id)
        assert metrics is not None
        assert metrics.refer_votes == 1

    def test_record_vote_escalate(self) -> None:
        """Test record_vote with ESCALATE outcome."""
        stub = AcknowledgmentRateMetricsStub()
        archon_id = uuid4()

        # Must have participation before voting (domain constraint)
        stub.record_participation(archon_id)
        stub.record_vote(archon_id, "ESCALATE")

        metrics = stub.get_metrics(archon_id)
        assert metrics is not None
        assert metrics.escalate_votes == 1

    def test_record_vote_tracks_calls(self) -> None:
        """Test vote calls are tracked."""
        stub = AcknowledgmentRateMetricsStub()
        archon_id = uuid4()

        # Must have participations before voting (domain constraint)
        stub.record_participation(archon_id)
        stub.record_vote(archon_id, "ACKNOWLEDGE")
        stub.record_participation(archon_id)
        stub.record_vote(archon_id, "REFER")

        assert len(stub.vote_calls) == 2
        assert stub.vote_calls[0] == (archon_id, "ACKNOWLEDGE")
        assert stub.vote_calls[1] == (archon_id, "REFER")

    def test_record_vote_invalid_outcome_raises(self) -> None:
        """Test record_vote raises ValueError for invalid outcome."""
        stub = AcknowledgmentRateMetricsStub()
        archon_id = uuid4()

        with pytest.raises(ValueError, match="Invalid outcome"):
            stub.record_vote(archon_id, "INVALID")

    def test_record_deliberation_completion(self) -> None:
        """Test record_deliberation_completion records all archons."""
        stub = AcknowledgmentRateMetricsStub()

        archon_1 = uuid4()
        archon_2 = uuid4()
        archon_3 = uuid4()

        archon_votes = {
            archon_1: "ACKNOWLEDGE",
            archon_2: "ACKNOWLEDGE",
            archon_3: "REFER",
        }

        stub.record_deliberation_completion(archon_votes)

        # Verify all archons have metrics
        for archon_id in [archon_1, archon_2, archon_3]:
            metrics = stub.get_metrics(archon_id)
            assert metrics is not None
            assert metrics.total_participations == 1

        # Verify vote counts
        assert stub.get_metrics(archon_1).acknowledge_votes == 1
        assert stub.get_metrics(archon_2).acknowledge_votes == 1
        assert stub.get_metrics(archon_3).refer_votes == 1

    def test_record_deliberation_completion_tracks_calls(self) -> None:
        """Test completion calls are tracked."""
        stub = AcknowledgmentRateMetricsStub()

        archon_votes = {uuid4(): "ACKNOWLEDGE"}
        stub.record_deliberation_completion(archon_votes)

        assert len(stub.completion_calls) == 1
        assert stub.completion_calls[0] == archon_votes

    def test_get_metrics_unknown_archon_returns_none(self) -> None:
        """Test get_metrics returns None for unknown archon."""
        stub = AcknowledgmentRateMetricsStub()

        metrics = stub.get_metrics(uuid4())
        assert metrics is None

    def test_get_all_metrics_returns_copy(self) -> None:
        """Test get_all_metrics returns all tracked metrics."""
        stub = AcknowledgmentRateMetricsStub()

        archon_1 = uuid4()
        archon_2 = uuid4()

        stub.record_participation(archon_1)
        stub.record_participation(archon_2)

        all_metrics = stub.get_all_metrics()

        assert len(all_metrics) == 2
        assert archon_1 in all_metrics
        assert archon_2 in all_metrics

    def test_clear_removes_all_data(self) -> None:
        """Test clear removes all metrics and calls."""
        stub = AcknowledgmentRateMetricsStub()
        archon_id = uuid4()

        stub.record_participation(archon_id)
        stub.record_vote(archon_id, "ACKNOWLEDGE")
        stub.record_deliberation_completion({archon_id: "REFER"})

        stub.clear()

        assert stub.get_metrics(archon_id) is None
        assert len(stub.participation_calls) == 0
        assert len(stub.vote_calls) == 0
        assert len(stub.completion_calls) == 0

    def test_acknowledgment_rate_calculation(self) -> None:
        """Test acknowledgment rate from accumulated metrics."""
        stub = AcknowledgmentRateMetricsStub()
        archon_id = uuid4()

        # Simulate 10 deliberations: 7 ACKNOWLEDGE, 2 REFER, 1 ESCALATE
        for _ in range(7):
            stub.record_participation(archon_id)
            stub.record_vote(archon_id, "ACKNOWLEDGE")
        for _ in range(2):
            stub.record_participation(archon_id)
            stub.record_vote(archon_id, "REFER")
        stub.record_participation(archon_id)
        stub.record_vote(archon_id, "ESCALATE")

        metrics = stub.get_metrics(archon_id)
        assert metrics is not None
        assert metrics.total_participations == 10
        assert metrics.acknowledgment_rate == 0.7
