"""Unit tests for LegitimacyDecayPort interface.

Tests the port interface contract for automatic legitimacy decay
as specified in consent-gov-5-2 story.
"""

from typing import Protocol
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.legitimacy_decay_port import (
    LegitimacyDecayPort,
    DecayResult,
)
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.violation_severity import ViolationSeverity


class TestLegitimacyDecayPortProtocol:
    """Tests for LegitimacyDecayPort protocol definition."""

    def test_is_protocol(self) -> None:
        """LegitimacyDecayPort is a Protocol."""
        assert issubclass(LegitimacyDecayPort, Protocol)

    def test_has_process_violation_method(self) -> None:
        """LegitimacyDecayPort has process_violation method."""
        assert hasattr(LegitimacyDecayPort, "process_violation")

    def test_has_get_decay_history_method(self) -> None:
        """LegitimacyDecayPort has get_decay_history method."""
        assert hasattr(LegitimacyDecayPort, "get_decay_history")


class TestDecayResult:
    """Tests for DecayResult dataclass."""

    def test_decay_result_has_required_fields(self) -> None:
        """DecayResult has all required fields."""
        result = DecayResult(
            transition_occurred=True,
            new_state=None,  # Will be mocked in real tests
            violation_event_id=uuid4(),
            severity=ViolationSeverity.MINOR,
            bands_dropped=1,
        )

        assert result.transition_occurred is True
        assert result.violation_event_id is not None
        assert result.severity == ViolationSeverity.MINOR
        assert result.bands_dropped == 1

    def test_decay_result_no_transition(self) -> None:
        """DecayResult when no transition occurred (already terminal)."""
        result = DecayResult(
            transition_occurred=False,
            new_state=None,
            violation_event_id=uuid4(),
            severity=ViolationSeverity.INTEGRITY,
            bands_dropped=0,
        )

        assert result.transition_occurred is False
        assert result.bands_dropped == 0

    def test_decay_result_is_frozen(self) -> None:
        """DecayResult is immutable."""
        result = DecayResult(
            transition_occurred=True,
            new_state=None,
            violation_event_id=uuid4(),
            severity=ViolationSeverity.MAJOR,
            bands_dropped=2,
        )

        with pytest.raises(AttributeError):
            result.transition_occurred = False  # type: ignore
