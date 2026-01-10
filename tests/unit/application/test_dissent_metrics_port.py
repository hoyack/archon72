"""Unit tests for DissentMetricsPort interface (Story 2.4, FR12).

Tests the DissentMetricsPort Protocol and DissentRecord dataclass
for tracking dissent metrics over time.

Test categories:
- DissentRecord dataclass validation
- Protocol method signatures
- Type checking
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.dissent_metrics import DissentMetricsPort, DissentRecord


class TestDissentRecord:
    """Tests for DissentRecord dataclass."""

    def test_valid_dissent_record(self) -> None:
        """Valid DissentRecord is created successfully."""
        output_id = uuid4()
        recorded_at = datetime.now(timezone.utc)

        record = DissentRecord(
            output_id=output_id,
            dissent_percentage=15.5,
            recorded_at=recorded_at,
        )

        assert record.output_id == output_id
        assert record.dissent_percentage == 15.5
        assert record.recorded_at == recorded_at

    def test_zero_dissent_percentage(self) -> None:
        """Zero dissent percentage (unanimous vote) is valid."""
        record = DissentRecord(
            output_id=uuid4(),
            dissent_percentage=0.0,
            recorded_at=datetime.now(timezone.utc),
        )

        assert record.dissent_percentage == 0.0

    def test_max_dissent_percentage(self) -> None:
        """50% dissent (maximum possible - split vote) is valid."""
        record = DissentRecord(
            output_id=uuid4(),
            dissent_percentage=50.0,
            recorded_at=datetime.now(timezone.utc),
        )

        assert record.dissent_percentage == 50.0

    def test_dissent_record_is_frozen(self) -> None:
        """DissentRecord is immutable (frozen dataclass)."""
        record = DissentRecord(
            output_id=uuid4(),
            dissent_percentage=15.0,
            recorded_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            record.dissent_percentage = 20.0  # type: ignore[misc]

    def test_rejects_negative_dissent_percentage(self) -> None:
        """Rejects negative dissent percentage."""
        with pytest.raises(ValueError, match="dissent_percentage"):
            DissentRecord(
                output_id=uuid4(),
                dissent_percentage=-5.0,
                recorded_at=datetime.now(timezone.utc),
            )

    def test_rejects_dissent_percentage_over_100(self) -> None:
        """Rejects dissent percentage over 100."""
        with pytest.raises(ValueError, match="dissent_percentage"):
            DissentRecord(
                output_id=uuid4(),
                dissent_percentage=150.0,
                recorded_at=datetime.now(timezone.utc),
            )

    def test_to_dict_serialization(self) -> None:
        """to_dict() produces correct dictionary structure."""
        output_id = uuid4()
        recorded_at = datetime.now(timezone.utc)

        record = DissentRecord(
            output_id=output_id,
            dissent_percentage=25.5,
            recorded_at=recorded_at,
        )

        result = record.to_dict()

        assert result["output_id"] == str(output_id)
        assert result["dissent_percentage"] == 25.5
        assert result["recorded_at"] == recorded_at.isoformat()


class TestDissentMetricsPortProtocol:
    """Tests for DissentMetricsPort Protocol interface."""

    def test_protocol_has_record_vote_dissent_method(self) -> None:
        """Protocol defines record_vote_dissent method."""
        assert hasattr(DissentMetricsPort, "record_vote_dissent")

    def test_protocol_has_get_rolling_average_method(self) -> None:
        """Protocol defines get_rolling_average method."""
        assert hasattr(DissentMetricsPort, "get_rolling_average")

    def test_protocol_has_get_dissent_history_method(self) -> None:
        """Protocol defines get_dissent_history method."""
        assert hasattr(DissentMetricsPort, "get_dissent_history")

    def test_protocol_has_is_below_threshold_method(self) -> None:
        """Protocol defines is_below_threshold method."""
        assert hasattr(DissentMetricsPort, "is_below_threshold")
