"""Unit tests for Keeper availability event payloads (Story 5.8, AC2).

Tests the event payloads for:
- KeeperAttestationPayload
- KeeperMissedAttestationPayload
- KeeperReplacementInitiatedPayload
- KeeperQuorumWarningPayload

Constitutional Constraints:
- FR78: Weekly attestation requirement
- FR79: Minimum 3 Keepers (quorum)
- SR-7: Alert when quorum drops to 3
"""

import json
from datetime import datetime, timezone

from src.domain.events.keeper_availability import (
    KEEPER_ATTESTATION_EVENT_TYPE,
    KEEPER_MISSED_ATTESTATION_EVENT_TYPE,
    KEEPER_QUORUM_WARNING_EVENT_TYPE,
    KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE,
    AlertSeverity,
    KeeperAttestationPayload,
    KeeperMissedAttestationPayload,
    KeeperQuorumWarningPayload,
    KeeperReplacementInitiatedPayload,
)


class TestKeeperAttestationPayload:
    """Test KeeperAttestationPayload event."""

    def test_create_valid_payload(self) -> None:
        """Test creating a valid attestation payload."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)

        payload = KeeperAttestationPayload(
            keeper_id="KEEPER:alice",
            attested_at=now,
            attestation_period_start=period_start,
            attestation_period_end=period_end,
        )

        assert payload.keeper_id == "KEEPER:alice"
        assert payload.attested_at == now
        assert payload.attestation_period_start == period_start
        assert payload.attestation_period_end == period_end

    def test_signable_content_is_deterministic(self) -> None:
        """Test that signable_content produces deterministic bytes."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)

        payload = KeeperAttestationPayload(
            keeper_id="KEEPER:alice",
            attested_at=now,
            attestation_period_start=period_start,
            attestation_period_end=period_end,
            timestamp=now,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_signable_content_contains_event_type(self) -> None:
        """Test that signable_content includes event type."""
        now = datetime.now(timezone.utc)

        payload = KeeperAttestationPayload(
            keeper_id="KEEPER:alice",
            attested_at=now,
            attestation_period_start=now,
            attestation_period_end=now,
        )

        content = payload.signable_content()
        content_dict = json.loads(content.decode("utf-8"))

        assert content_dict["event_type"] == KEEPER_ATTESTATION_EVENT_TYPE

    def test_to_dict_returns_serializable_dict(self) -> None:
        """Test that to_dict returns JSON-serializable dict."""
        now = datetime.now(timezone.utc)

        payload = KeeperAttestationPayload(
            keeper_id="KEEPER:alice",
            attested_at=now,
            attestation_period_start=now,
            attestation_period_end=now,
        )

        result = payload.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert json_str is not None
        assert result["keeper_id"] == "KEEPER:alice"


class TestKeeperMissedAttestationPayload:
    """Test KeeperMissedAttestationPayload event."""

    def test_create_valid_payload(self) -> None:
        """Test creating a valid missed attestation payload."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)

        payload = KeeperMissedAttestationPayload(
            keeper_id="KEEPER:bob",
            missed_period_start=period_start,
            missed_period_end=period_end,
            consecutive_misses=1,
            deadline_passed_at=now,
        )

        assert payload.keeper_id == "KEEPER:bob"
        assert payload.consecutive_misses == 1
        assert payload.missed_period_start == period_start

    def test_signable_content_includes_consecutive_misses(self) -> None:
        """Test that signable_content includes consecutive_misses."""
        now = datetime.now(timezone.utc)

        payload = KeeperMissedAttestationPayload(
            keeper_id="KEEPER:bob",
            missed_period_start=now,
            missed_period_end=now,
            consecutive_misses=2,
            deadline_passed_at=now,
        )

        content = payload.signable_content()
        content_dict = json.loads(content.decode("utf-8"))

        assert content_dict["consecutive_misses"] == 2
        assert content_dict["event_type"] == KEEPER_MISSED_ATTESTATION_EVENT_TYPE


class TestKeeperReplacementInitiatedPayload:
    """Test KeeperReplacementInitiatedPayload event."""

    def test_create_valid_payload(self) -> None:
        """Test creating a valid replacement initiated payload."""
        now = datetime.now(timezone.utc)
        missed_periods = (
            ("2025-01-06T00:00:00+00:00", "2025-01-13T00:00:00+00:00"),
            ("2025-01-13T00:00:00+00:00", "2025-01-20T00:00:00+00:00"),
        )

        payload = KeeperReplacementInitiatedPayload(
            keeper_id="KEEPER:bob",
            missed_periods=missed_periods,
            initiated_at=now,
            reason="FR78: Missed 2 consecutive attestations",
        )

        assert payload.keeper_id == "KEEPER:bob"
        assert len(payload.missed_periods) == 2
        assert "FR78" in payload.reason

    def test_missed_periods_converted_to_tuple(self) -> None:
        """Test that lists are converted to tuples for immutability."""
        now = datetime.now(timezone.utc)
        # Pass as lists to test conversion
        missed_periods = [
            ["2025-01-06T00:00:00+00:00", "2025-01-13T00:00:00+00:00"],
            ["2025-01-13T00:00:00+00:00", "2025-01-20T00:00:00+00:00"],
        ]

        payload = KeeperReplacementInitiatedPayload(
            keeper_id="KEEPER:bob",
            missed_periods=missed_periods,  # type: ignore[arg-type]
            initiated_at=now,
            reason="FR78: Missed 2 consecutive attestations",
        )

        # Should be converted to tuple of tuples
        assert isinstance(payload.missed_periods, tuple)
        assert all(isinstance(p, tuple) for p in payload.missed_periods)

    def test_signable_content_contains_event_type(self) -> None:
        """Test that signable_content includes event type."""
        now = datetime.now(timezone.utc)
        missed_periods = (("start1", "end1"),)

        payload = KeeperReplacementInitiatedPayload(
            keeper_id="KEEPER:bob",
            missed_periods=missed_periods,
            initiated_at=now,
            reason="test reason",
        )

        content = payload.signable_content()
        content_dict = json.loads(content.decode("utf-8"))

        assert content_dict["event_type"] == KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE


class TestKeeperQuorumWarningPayload:
    """Test KeeperQuorumWarningPayload event (SR-7)."""

    def test_create_valid_payload(self) -> None:
        """Test creating a valid quorum warning payload."""
        payload = KeeperQuorumWarningPayload(
            current_count=3,
            minimum_required=3,
            alert_severity=AlertSeverity.MEDIUM.value,
        )

        assert payload.current_count == 3
        assert payload.minimum_required == 3
        assert payload.alert_severity == "MEDIUM"

    def test_signable_content_contains_event_type(self) -> None:
        """Test that signable_content includes event type."""
        payload = KeeperQuorumWarningPayload(
            current_count=3,
            minimum_required=3,
            alert_severity=AlertSeverity.MEDIUM.value,
        )

        content = payload.signable_content()
        content_dict = json.loads(content.decode("utf-8"))

        assert content_dict["event_type"] == KEEPER_QUORUM_WARNING_EVENT_TYPE

    def test_to_dict_returns_serializable_dict(self) -> None:
        """Test that to_dict returns JSON-serializable dict."""
        payload = KeeperQuorumWarningPayload(
            current_count=3,
            minimum_required=3,
            alert_severity=AlertSeverity.HIGH.value,
        )

        result = payload.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert json_str is not None
        assert result["current_count"] == 3
        assert result["minimum_required"] == 3


class TestAlertSeverity:
    """Test AlertSeverity enum."""

    def test_severity_levels_exist(self) -> None:
        """Test that all severity levels exist."""
        assert AlertSeverity.LOW.value == "LOW"
        assert AlertSeverity.MEDIUM.value == "MEDIUM"
        assert AlertSeverity.HIGH.value == "HIGH"
        assert AlertSeverity.CRITICAL.value == "CRITICAL"


class TestEventTypeConstants:
    """Test event type constants."""

    def test_attestation_event_type(self) -> None:
        """Test KEEPER_ATTESTATION_EVENT_TYPE constant."""
        assert KEEPER_ATTESTATION_EVENT_TYPE == "keeper.attestation.submitted"

    def test_missed_attestation_event_type(self) -> None:
        """Test KEEPER_MISSED_ATTESTATION_EVENT_TYPE constant."""
        assert KEEPER_MISSED_ATTESTATION_EVENT_TYPE == "keeper.attestation.missed"

    def test_replacement_initiated_event_type(self) -> None:
        """Test KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE constant."""
        assert KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE == "keeper.replacement.initiated"

    def test_quorum_warning_event_type(self) -> None:
        """Test KEEPER_QUORUM_WARNING_EVENT_TYPE constant."""
        assert KEEPER_QUORUM_WARNING_EVENT_TYPE == "keeper.quorum.warning"
