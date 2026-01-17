"""Unit tests for restoration acknowledgment domain models.

Tests the domain models used for explicit legitimacy restoration.

Constitutional Compliance:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- AC7: Acknowledgment includes reason and evidence
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.legitimacy.restoration_acknowledgment import (
    RestorationAcknowledgment,
    RestorationRequest,
    RestorationResult,
)
from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.transition_type import TransitionType


class TestRestorationAcknowledgmentProperties:
    """Tests for RestorationAcknowledgment computed properties."""

    def test_severity_improvement_single_step(self) -> None:
        """Single step restoration has severity improvement of 1."""
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            reason="Resolved",
            evidence="Evidence",
            acknowledged_at=datetime.now(timezone.utc),
        )

        assert ack.severity_improvement == 1

    def test_severity_improvement_multi_step(self) -> None:
        """Multi-step restoration has severity improvement > 1."""
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=LegitimacyBand.COMPROMISED,
            to_band=LegitimacyBand.STABLE,
            reason="All issues resolved",
            evidence="Comprehensive audit",
            acknowledged_at=datetime.now(timezone.utc),
        )

        assert ack.severity_improvement == 3

    def test_is_single_step_true(self) -> None:
        """is_single_step returns True for one-band improvement."""
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=LegitimacyBand.ERODING,
            to_band=LegitimacyBand.STRAINED,
            reason="Issues addressed",
            evidence="Audit",
            acknowledged_at=datetime.now(timezone.utc),
        )

        assert ack.is_single_step is True

    def test_is_single_step_false(self) -> None:
        """is_single_step returns False for multi-band improvement."""
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=LegitimacyBand.ERODING,
            to_band=LegitimacyBand.STABLE,
            reason="All issues addressed",
            evidence="Complete audit",
            acknowledged_at=datetime.now(timezone.utc),
        )

        assert ack.is_single_step is False


class TestRestorationAcknowledgmentFromDomain:
    """Tests importing from domain module."""

    def test_import_from_domain_module(self) -> None:
        """Can import models from legitimacy domain module."""
        from src.domain.governance.legitimacy import (
            RestorationAcknowledgment,
            RestorationRequest,
            RestorationResult,
        )

        # Verify we can create instances
        ack = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=uuid4(),
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            reason="Test",
            evidence="Evidence",
            acknowledged_at=datetime.now(timezone.utc),
        )
        assert ack is not None


class TestRestorationRequestValidation:
    """Additional validation tests for RestorationRequest."""

    def test_request_accepts_any_target_band(self) -> None:
        """Request model accepts any band as target."""
        # The service will validate against current state
        # The model just captures the request
        for band in LegitimacyBand:
            request = RestorationRequest(
                operator_id=uuid4(),
                target_band=band,
                reason="Valid reason",
                evidence="Valid evidence",
            )
            assert request.target_band == band

    def test_request_preserves_original_text(self) -> None:
        """Request preserves exact reason and evidence text."""
        reason = "  Detailed reason with   spaces  "
        evidence = "  Evidence ID: 123  "

        request = RestorationRequest(
            operator_id=uuid4(),
            target_band=LegitimacyBand.STABLE,
            reason=reason,
            evidence=evidence,
        )

        assert request.reason == reason
        assert request.evidence == evidence


class TestRestorationResultDetails:
    """Additional tests for RestorationResult."""

    def test_failed_result_has_no_state(self) -> None:
        """Failed result has no new_state."""
        result = RestorationResult.failed("Error message")

        assert result.new_state is None
        assert result.acknowledgment is None

    def test_succeeded_result_has_all_fields(self) -> None:
        """Successful result has all required fields."""
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
        assert result.new_state is not None
        assert result.new_state.current_band == LegitimacyBand.STABLE
        assert result.acknowledgment is not None
        assert result.error is None

    def test_result_direct_construction(self) -> None:
        """Can construct result directly (edge cases)."""
        # Edge case: manual construction
        result = RestorationResult(
            success=False,
            new_state=None,
            acknowledgment=None,
            error="Manual error",
        )

        assert result.success is False
        assert result.error == "Manual error"
