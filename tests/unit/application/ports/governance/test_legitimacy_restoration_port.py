"""Unit tests for LegitimacyRestorationPort interface and domain models.

Tests the restoration port interface contracts and the domain models
used for explicit legitimacy restoration.

Constitutional Compliance:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.governance.legitimacy_restoration_port import (
    LegitimacyRestorationPort,
    RestorationAcknowledgment,
    RestorationRequest,
    RestorationResult,
)
from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.transition_type import TransitionType


class TestRestorationAcknowledgment:
    """Tests for RestorationAcknowledgment domain model."""

    def test_valid_acknowledgment_creation(self) -> None:
        """Acknowledgment with valid parameters succeeds."""
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            reason="Issues have been resolved",
            evidence="Audit ID: AUD-2026-0117",
            acknowledged_at=datetime.now(timezone.utc),
        )

        assert ack.from_band == LegitimacyBand.STRAINED
        assert ack.to_band == LegitimacyBand.STABLE
        assert "resolved" in ack.reason.lower()

    def test_acknowledgment_requires_reason(self) -> None:
        """Acknowledgment must have a non-empty reason."""
        with pytest.raises(ValueError, match="[Rr]eason.*required"):
            RestorationAcknowledgment(
                acknowledgment_id=uuid4(),
                operator_id=uuid4(),
                from_band=LegitimacyBand.STRAINED,
                to_band=LegitimacyBand.STABLE,
                reason="",
                evidence="Some evidence",
                acknowledged_at=datetime.now(timezone.utc),
            )

    def test_acknowledgment_requires_evidence(self) -> None:
        """Acknowledgment must have non-empty evidence."""
        with pytest.raises(ValueError, match="[Ee]vidence.*required"):
            RestorationAcknowledgment(
                acknowledgment_id=uuid4(),
                operator_id=uuid4(),
                from_band=LegitimacyBand.STRAINED,
                to_band=LegitimacyBand.STABLE,
                reason="Valid reason",
                evidence="",
                acknowledged_at=datetime.now(timezone.utc),
            )

    def test_acknowledgment_whitespace_reason_rejected(self) -> None:
        """Whitespace-only reason is rejected."""
        with pytest.raises(ValueError, match="[Rr]eason.*required"):
            RestorationAcknowledgment(
                acknowledgment_id=uuid4(),
                operator_id=uuid4(),
                from_band=LegitimacyBand.STRAINED,
                to_band=LegitimacyBand.STABLE,
                reason="   ",
                evidence="Valid evidence",
                acknowledged_at=datetime.now(timezone.utc),
            )

    def test_acknowledgment_whitespace_evidence_rejected(self) -> None:
        """Whitespace-only evidence is rejected."""
        with pytest.raises(ValueError, match="[Ee]vidence.*required"):
            RestorationAcknowledgment(
                acknowledgment_id=uuid4(),
                operator_id=uuid4(),
                from_band=LegitimacyBand.STRAINED,
                to_band=LegitimacyBand.STABLE,
                reason="Valid reason",
                evidence="\t\n",
                acknowledged_at=datetime.now(timezone.utc),
            )

    def test_acknowledgment_must_be_upward(self) -> None:
        """Acknowledgment must be for upward transition (lower severity)."""
        with pytest.raises(ValueError, match="[Uu]pward"):
            RestorationAcknowledgment(
                acknowledgment_id=uuid4(),
                operator_id=uuid4(),
                from_band=LegitimacyBand.STABLE,
                to_band=LegitimacyBand.STRAINED,  # Wrong direction
                reason="Trying to go down",
                evidence="Evidence",
                acknowledged_at=datetime.now(timezone.utc),
            )

    def test_acknowledgment_same_band_rejected(self) -> None:
        """Acknowledgment for same band (no change) is rejected."""
        with pytest.raises(ValueError, match="[Uu]pward"):
            RestorationAcknowledgment(
                acknowledgment_id=uuid4(),
                operator_id=uuid4(),
                from_band=LegitimacyBand.STABLE,
                to_band=LegitimacyBand.STABLE,
                reason="No change",
                evidence="Evidence",
                acknowledged_at=datetime.now(timezone.utc),
            )

    def test_acknowledgment_is_immutable(self) -> None:
        """Acknowledgment is a frozen dataclass."""
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            reason="Resolved",
            evidence="Evidence",
            acknowledged_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            ack.reason = "Modified"  # type: ignore


class TestRestorationRequest:
    """Tests for RestorationRequest domain model."""

    def test_valid_request_creation(self) -> None:
        """Request with valid parameters succeeds."""
        request = RestorationRequest(
            operator_id=uuid4(),
            target_band=LegitimacyBand.STABLE,
            reason="All issues resolved",
            evidence="Audit complete: AUD-123",
        )

        assert request.target_band == LegitimacyBand.STABLE
        assert "resolved" in request.reason.lower()

    def test_request_requires_reason(self) -> None:
        """Request must have non-empty reason."""
        with pytest.raises(ValueError, match="[Rr]eason.*required"):
            RestorationRequest(
                operator_id=uuid4(),
                target_band=LegitimacyBand.STABLE,
                reason="",
                evidence="Valid evidence",
            )

    def test_request_requires_evidence(self) -> None:
        """Request must have non-empty evidence."""
        with pytest.raises(ValueError, match="[Ee]vidence.*required"):
            RestorationRequest(
                operator_id=uuid4(),
                target_band=LegitimacyBand.STABLE,
                reason="Valid reason",
                evidence="",
            )

    def test_request_is_immutable(self) -> None:
        """Request is a frozen dataclass."""
        request = RestorationRequest(
            operator_id=uuid4(),
            target_band=LegitimacyBand.STABLE,
            reason="Reason",
            evidence="Evidence",
        )

        with pytest.raises(AttributeError):
            request.reason = "Modified"  # type: ignore


class TestRestorationResult:
    """Tests for RestorationResult domain model."""

    def test_succeeded_factory(self) -> None:
        """RestorationResult.succeeded() creates success result."""
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            reason="Resolved",
            evidence="Evidence",
            acknowledged_at=datetime.now(timezone.utc),
        )
        state = LegitimacyState(
            current_band=LegitimacyBand.STABLE,
            entered_at=datetime.now(timezone.utc),
            violation_count=5,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.ACKNOWLEDGED,
        )

        result = RestorationResult.succeeded(state, ack)

        assert result.success is True
        assert result.new_state == state
        assert result.acknowledgment == ack
        assert result.error is None

    def test_failed_factory(self) -> None:
        """RestorationResult.failed() creates failure result."""
        result = RestorationResult.failed(
            "FAILED is terminal - reconstitution required"
        )

        assert result.success is False
        assert result.new_state is None
        assert result.acknowledgment is None
        assert "terminal" in result.error.lower()

    def test_result_is_immutable(self) -> None:
        """RestorationResult is a frozen dataclass."""
        result = RestorationResult.failed("Error")

        with pytest.raises(AttributeError):
            result.success = True  # type: ignore


class TestLegitimacyRestorationPortProtocol:
    """Tests verifying the port protocol is properly defined."""

    def test_port_is_protocol(self) -> None:
        """LegitimacyRestorationPort is a Protocol class."""
        from typing import Protocol

        assert issubclass(LegitimacyRestorationPort, Protocol)

    def test_port_has_request_restoration_method(self) -> None:
        """Port defines request_restoration method."""
        assert hasattr(LegitimacyRestorationPort, "request_restoration")

    def test_port_has_get_restoration_history_method(self) -> None:
        """Port defines get_restoration_history method."""
        assert hasattr(LegitimacyRestorationPort, "get_restoration_history")

    def test_port_has_get_acknowledgment_method(self) -> None:
        """Port defines get_acknowledgment method."""
        assert hasattr(LegitimacyRestorationPort, "get_acknowledgment")

    def test_port_has_get_restoration_count_method(self) -> None:
        """Port defines get_restoration_count method."""
        assert hasattr(LegitimacyRestorationPort, "get_restoration_count")


class TestRestorationAcknowledgmentAllBandTransitions:
    """Test acknowledgment creation for all valid band transitions."""

    @pytest.mark.parametrize(
        "from_band,to_band",
        [
            (LegitimacyBand.STRAINED, LegitimacyBand.STABLE),
            (LegitimacyBand.ERODING, LegitimacyBand.STRAINED),
            (LegitimacyBand.COMPROMISED, LegitimacyBand.ERODING),
            # Note: FAILED → anything is blocked at service level, not model level
        ],
    )
    def test_valid_one_step_up_transitions(
        self, from_band: LegitimacyBand, to_band: LegitimacyBand
    ) -> None:
        """Each one-step-up transition can create valid acknowledgment."""
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=from_band,
            to_band=to_band,
            reason="Issues addressed",
            evidence="Audit complete",
            acknowledged_at=datetime.now(timezone.utc),
        )

        assert ack.from_band.severity - ack.to_band.severity == 1

    @pytest.mark.parametrize(
        "from_band,to_band,severity_diff",
        [
            (LegitimacyBand.ERODING, LegitimacyBand.STABLE, 2),  # Skip STRAINED
            (LegitimacyBand.COMPROMISED, LegitimacyBand.STRAINED, 2),  # Skip ERODING
            (LegitimacyBand.COMPROMISED, LegitimacyBand.STABLE, 3),  # Skip 2 bands
        ],
    )
    def test_multi_step_acknowledgments_allowed_at_model_level(
        self, from_band: LegitimacyBand, to_band: LegitimacyBand, severity_diff: int
    ) -> None:
        """Acknowledgment model allows multi-step; service enforces one-step constraint."""
        # The model allows this - the service will reject multi-step attempts
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=from_band,
            to_band=to_band,
            reason="All issues addressed at once",
            evidence="Comprehensive audit",
            acknowledged_at=datetime.now(timezone.utc),
        )

        assert ack.from_band.severity - ack.to_band.severity == severity_diff
