"""Unit tests for collusion investigation domain events (Story 6.8, FR124).

Tests CollusionInvestigationTriggeredEventPayload, WitnessPairSuspendedEventPayload,
and InvestigationResolvedEventPayload.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.domain.events.collusion import (
    COLLUSION_INVESTIGATION_TRIGGERED_EVENT_TYPE,
    INVESTIGATION_RESOLVED_EVENT_TYPE,
    WITNESS_PAIR_SUSPENDED_EVENT_TYPE,
    CollusionInvestigationTriggeredEventPayload,
    InvestigationResolution,
    InvestigationResolvedEventPayload,
    WitnessPairSuspendedEventPayload,
)


class TestCollusionInvestigationTriggeredEventPayload:
    """Tests for CollusionInvestigationTriggeredEventPayload."""

    def test_create_valid_payload(self) -> None:
        """Test creating a valid investigation triggered payload."""
        now = datetime.now(timezone.utc)
        payload = CollusionInvestigationTriggeredEventPayload(
            investigation_id="inv-123",
            witness_pair_key="witness_a:witness_b",
            triggering_anomalies=("anomaly-1", "anomaly-2"),
            breach_event_ids=("breach-1", "breach-2"),
            correlation_score=0.85,
            triggered_at=now,
            triggered_by="system:collusion_defense",
        )

        assert payload.investigation_id == "inv-123"
        assert payload.witness_pair_key == "witness_a:witness_b"
        assert payload.triggering_anomalies == ("anomaly-1", "anomaly-2")
        assert payload.breach_event_ids == ("breach-1", "breach-2")
        assert payload.correlation_score == 0.85
        assert payload.triggered_at == now
        assert payload.triggered_by == "system:collusion_defense"

    def test_correlation_score_validation(self) -> None:
        """Test that correlation score must be between 0.0 and 1.0."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="correlation_score must be between"):
            CollusionInvestigationTriggeredEventPayload(
                investigation_id="inv-123",
                witness_pair_key="witness_a:witness_b",
                triggering_anomalies=("anomaly-1",),
                breach_event_ids=("breach-1",),
                correlation_score=1.5,
                triggered_at=now,
                triggered_by="system:collusion_defense",
            )

        with pytest.raises(ValueError, match="correlation_score must be between"):
            CollusionInvestigationTriggeredEventPayload(
                investigation_id="inv-123",
                witness_pair_key="witness_a:witness_b",
                triggering_anomalies=("anomaly-1",),
                breach_event_ids=("breach-1",),
                correlation_score=-0.1,
                triggered_at=now,
                triggered_by="system:collusion_defense",
            )

    def test_empty_investigation_id_validation(self) -> None:
        """Test that investigation_id cannot be empty."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="investigation_id cannot be empty"):
            CollusionInvestigationTriggeredEventPayload(
                investigation_id="",
                witness_pair_key="witness_a:witness_b",
                triggering_anomalies=("anomaly-1",),
                breach_event_ids=("breach-1",),
                correlation_score=0.85,
                triggered_at=now,
                triggered_by="system:collusion_defense",
            )

    def test_signable_content(self) -> None:
        """Test signable_content produces deterministic JSON (CT-12)."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = CollusionInvestigationTriggeredEventPayload(
            investigation_id="inv-123",
            witness_pair_key="witness_a:witness_b",
            triggering_anomalies=("anomaly-1", "anomaly-2"),
            breach_event_ids=("breach-1",),
            correlation_score=0.85,
            triggered_at=now,
            triggered_by="system:collusion_defense",
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

        # Should be valid JSON
        data = json.loads(content.decode("utf-8"))
        assert data["event_type"] == COLLUSION_INVESTIGATION_TRIGGERED_EVENT_TYPE
        assert data["investigation_id"] == "inv-123"
        assert data["correlation_score"] == 0.85

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        now = datetime.now(timezone.utc)
        payload = CollusionInvestigationTriggeredEventPayload(
            investigation_id="inv-123",
            witness_pair_key="witness_a:witness_b",
            triggering_anomalies=("anomaly-1",),
            breach_event_ids=("breach-1",),
            correlation_score=0.85,
            triggered_at=now,
            triggered_by="system:collusion_defense",
        )

        data = payload.to_dict()
        assert data["investigation_id"] == "inv-123"
        assert data["witness_pair_key"] == "witness_a:witness_b"
        assert data["triggering_anomalies"] == ["anomaly-1"]
        assert data["breach_event_ids"] == ["breach-1"]
        assert data["correlation_score"] == 0.85

    def test_frozen_immutability(self) -> None:
        """Test that payload is immutable (frozen dataclass)."""
        now = datetime.now(timezone.utc)
        payload = CollusionInvestigationTriggeredEventPayload(
            investigation_id="inv-123",
            witness_pair_key="witness_a:witness_b",
            triggering_anomalies=("anomaly-1",),
            breach_event_ids=("breach-1",),
            correlation_score=0.85,
            triggered_at=now,
            triggered_by="system:collusion_defense",
        )

        with pytest.raises(AttributeError):
            payload.investigation_id = "inv-456"  # type: ignore


class TestWitnessPairSuspendedEventPayload:
    """Tests for WitnessPairSuspendedEventPayload."""

    def test_create_valid_payload(self) -> None:
        """Test creating a valid suspension payload."""
        now = datetime.now(timezone.utc)
        payload = WitnessPairSuspendedEventPayload(
            pair_key="witness_a:witness_b",
            investigation_id="inv-123",
            suspension_reason="FR124: Collusion investigation",
            suspended_at=now,
            suspended_by="system:collusion_defense",
        )

        assert payload.pair_key == "witness_a:witness_b"
        assert payload.investigation_id == "inv-123"
        assert payload.suspended_by == "system:collusion_defense"

    def test_empty_pair_key_validation(self) -> None:
        """Test that pair_key cannot be empty."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="pair_key cannot be empty"):
            WitnessPairSuspendedEventPayload(
                pair_key="",
                investigation_id="inv-123",
                suspension_reason="FR124: Collusion investigation",
                suspended_at=now,
                suspended_by="system:collusion_defense",
            )

    def test_signable_content(self) -> None:
        """Test signable_content produces deterministic JSON (CT-12)."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = WitnessPairSuspendedEventPayload(
            pair_key="witness_a:witness_b",
            investigation_id="inv-123",
            suspension_reason="FR124: Collusion investigation",
            suspended_at=now,
            suspended_by="system:collusion_defense",
        )

        content = payload.signable_content()
        data = json.loads(content.decode("utf-8"))
        assert data["event_type"] == WITNESS_PAIR_SUSPENDED_EVENT_TYPE
        assert data["pair_key"] == "witness_a:witness_b"


class TestInvestigationResolvedEventPayload:
    """Tests for InvestigationResolvedEventPayload."""

    def test_create_cleared_resolution(self) -> None:
        """Test creating a CLEARED resolution payload."""
        now = datetime.now(timezone.utc)
        payload = InvestigationResolvedEventPayload(
            investigation_id="inv-123",
            pair_key="witness_a:witness_b",
            resolution=InvestigationResolution.CLEARED,
            resolution_reason="No evidence of collusion found",
            resolved_at=now,
            resolved_by="human_reviewer_1",
            evidence_summary="Correlation score: 0.85, manual review cleared",
        )

        assert payload.resolution == InvestigationResolution.CLEARED
        assert payload.resolved_by == "human_reviewer_1"

    def test_create_confirmed_resolution(self) -> None:
        """Test creating a CONFIRMED_COLLUSION resolution payload."""
        now = datetime.now(timezone.utc)
        payload = InvestigationResolvedEventPayload(
            investigation_id="inv-123",
            pair_key="witness_a:witness_b",
            resolution=InvestigationResolution.CONFIRMED_COLLUSION,
            resolution_reason="Evidence confirmed coordinated behavior",
            resolved_at=now,
            resolved_by="human_reviewer_1",
            evidence_summary="Breach correlation confirmed",
        )

        assert payload.resolution == InvestigationResolution.CONFIRMED_COLLUSION

    def test_empty_resolved_by_validation(self) -> None:
        """Test that resolved_by cannot be empty (CT-12 attribution)."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="resolved_by cannot be empty"):
            InvestigationResolvedEventPayload(
                investigation_id="inv-123",
                pair_key="witness_a:witness_b",
                resolution=InvestigationResolution.CLEARED,
                resolution_reason="No evidence",
                resolved_at=now,
                resolved_by="",
                evidence_summary="",
            )

    def test_signable_content(self) -> None:
        """Test signable_content produces deterministic JSON (CT-12)."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = InvestigationResolvedEventPayload(
            investigation_id="inv-123",
            pair_key="witness_a:witness_b",
            resolution=InvestigationResolution.CLEARED,
            resolution_reason="No evidence",
            resolved_at=now,
            resolved_by="human_reviewer_1",
            evidence_summary="",
        )

        content = payload.signable_content()
        data = json.loads(content.decode("utf-8"))
        assert data["event_type"] == INVESTIGATION_RESOLVED_EVENT_TYPE
        assert data["resolution"] == "cleared"


class TestInvestigationResolution:
    """Tests for InvestigationResolution enum."""

    def test_enum_values(self) -> None:
        """Test enum has expected values."""
        assert InvestigationResolution.CLEARED.value == "cleared"
        assert (
            InvestigationResolution.CONFIRMED_COLLUSION.value == "confirmed_collusion"
        )
