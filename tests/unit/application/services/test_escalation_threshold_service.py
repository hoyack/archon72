"""Unit tests for EscalationThresholdService (Story 5.5, FR-5.2, FR-6.5).

Tests the escalation threshold checking service which determines when
petition co-signer counts reach escalation thresholds.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached
- FR-5.2: Escalation thresholds: CESSATION=100, GRIEVANCE=50
- FR-6.5: System SHALL check escalation threshold on each co-sign
- FR-10.2: CESSATION petitions SHALL auto-escalate at 100 co-signers
- FR-10.3: GRIEVANCE petitions SHALL auto-escalate at 50 co-signers
- CON-5: CESSATION auto-escalation threshold is immutable (100)
"""

from __future__ import annotations

import pytest

from src.application.ports.escalation_threshold import (
    EscalationThresholdCheckerProtocol,
    EscalationThresholdResult,
)
from src.application.services.escalation_threshold_service import (
    DEFAULT_CESSATION_THRESHOLD,
    DEFAULT_GRIEVANCE_THRESHOLD,
    EscalationThresholdService,
)
from src.domain.models.petition_submission import PetitionType


class TestEscalationThresholdServiceProtocol:
    """Test that EscalationThresholdService implements the protocol."""

    def test_implements_protocol(self) -> None:
        """EscalationThresholdService implements EscalationThresholdCheckerProtocol."""
        service = EscalationThresholdService()
        assert isinstance(service, EscalationThresholdCheckerProtocol)


class TestDefaultThresholds:
    """Test default threshold constants (FR-5.2, CON-5)."""

    def test_cessation_threshold_is_100(self) -> None:
        """CESSATION threshold is 100 per CON-5 (immutable)."""
        assert DEFAULT_CESSATION_THRESHOLD == 100

    def test_grievance_threshold_is_50(self) -> None:
        """GRIEVANCE threshold is 50 per FR-5.2."""
        assert DEFAULT_GRIEVANCE_THRESHOLD == 50


class TestGetThresholdForType:
    """Test get_threshold_for_type method."""

    def test_cessation_threshold(self) -> None:
        """CESSATION type returns 100 threshold."""
        service = EscalationThresholdService()
        threshold = service.get_threshold_for_type(PetitionType.CESSATION)
        assert threshold == 100

    def test_grievance_threshold(self) -> None:
        """GRIEVANCE type returns 50 threshold."""
        service = EscalationThresholdService()
        threshold = service.get_threshold_for_type(PetitionType.GRIEVANCE)
        assert threshold == 50

    def test_general_no_threshold(self) -> None:
        """GENERAL type returns None (no auto-escalation)."""
        service = EscalationThresholdService()
        threshold = service.get_threshold_for_type(PetitionType.GENERAL)
        assert threshold is None

    def test_collaboration_no_threshold(self) -> None:
        """COLLABORATION type returns None (no auto-escalation)."""
        service = EscalationThresholdService()
        threshold = service.get_threshold_for_type(PetitionType.COLLABORATION)
        assert threshold is None


class TestThresholdProperties:
    """Test threshold property accessors."""

    def test_cessation_threshold_property(self) -> None:
        """cessation_threshold property returns configured value."""
        service = EscalationThresholdService()
        assert service.cessation_threshold == 100

    def test_grievance_threshold_property(self) -> None:
        """grievance_threshold property returns configured value."""
        service = EscalationThresholdService()
        assert service.grievance_threshold == 50

    def test_custom_thresholds(self) -> None:
        """Custom thresholds can be passed at construction."""
        service = EscalationThresholdService(
            cessation_threshold=200,
            grievance_threshold=75,
        )
        assert service.cessation_threshold == 200
        assert service.grievance_threshold == 75


class TestCheckThresholdCessation:
    """Test threshold checking for CESSATION petitions (FR-10.2, CON-5)."""

    def test_below_threshold(self) -> None:
        """Returns threshold_reached=False when count < 100."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.CESSATION, 99)

        assert isinstance(result, EscalationThresholdResult)
        assert result.threshold_reached is False
        assert result.threshold_value == 100
        assert result.petition_type == "CESSATION"
        assert result.current_count == 99

    def test_at_threshold(self) -> None:
        """Returns threshold_reached=True when count == 100 (FR-10.2)."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.CESSATION, 100)

        assert result.threshold_reached is True
        assert result.threshold_value == 100
        assert result.current_count == 100

    def test_above_threshold(self) -> None:
        """Returns threshold_reached=True when count > 100."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.CESSATION, 150)

        assert result.threshold_reached is True
        assert result.threshold_value == 100
        assert result.current_count == 150

    def test_zero_count(self) -> None:
        """Returns threshold_reached=False when count is 0."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.CESSATION, 0)

        assert result.threshold_reached is False
        assert result.threshold_value == 100
        assert result.current_count == 0


class TestCheckThresholdGrievance:
    """Test threshold checking for GRIEVANCE petitions (FR-10.3)."""

    def test_below_threshold(self) -> None:
        """Returns threshold_reached=False when count < 50."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.GRIEVANCE, 49)

        assert result.threshold_reached is False
        assert result.threshold_value == 50
        assert result.petition_type == "GRIEVANCE"
        assert result.current_count == 49

    def test_at_threshold(self) -> None:
        """Returns threshold_reached=True when count == 50 (FR-10.3)."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.GRIEVANCE, 50)

        assert result.threshold_reached is True
        assert result.threshold_value == 50
        assert result.current_count == 50

    def test_above_threshold(self) -> None:
        """Returns threshold_reached=True when count > 50."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.GRIEVANCE, 75)

        assert result.threshold_reached is True
        assert result.threshold_value == 50
        assert result.current_count == 75


class TestCheckThresholdGeneral:
    """Test threshold checking for GENERAL petitions (no threshold)."""

    def test_no_threshold_at_zero(self) -> None:
        """GENERAL type returns threshold_reached=False always."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.GENERAL, 0)

        assert result.threshold_reached is False
        assert result.threshold_value is None
        assert result.petition_type == "GENERAL"
        assert result.current_count == 0

    def test_no_threshold_at_high_count(self) -> None:
        """GENERAL type returns threshold_reached=False even with high count."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.GENERAL, 1000)

        assert result.threshold_reached is False
        assert result.threshold_value is None
        assert result.current_count == 1000


class TestCheckThresholdCollaboration:
    """Test threshold checking for COLLABORATION petitions (no threshold)."""

    def test_no_threshold_at_zero(self) -> None:
        """COLLABORATION type returns threshold_reached=False always."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.COLLABORATION, 0)

        assert result.threshold_reached is False
        assert result.threshold_value is None
        assert result.petition_type == "COLLABORATION"

    def test_no_threshold_at_high_count(self) -> None:
        """COLLABORATION type returns threshold_reached=False even with high count."""
        service = EscalationThresholdService()
        result = service.check_threshold(PetitionType.COLLABORATION, 500)

        assert result.threshold_reached is False
        assert result.threshold_value is None


class TestEscalationThresholdResult:
    """Test EscalationThresholdResult dataclass."""

    def test_frozen(self) -> None:
        """EscalationThresholdResult is immutable."""
        result = EscalationThresholdResult(
            threshold_reached=True,
            threshold_value=100,
            petition_type="CESSATION",
            current_count=100,
        )
        with pytest.raises(AttributeError):
            result.threshold_reached = False  # type: ignore[misc]

    def test_equality(self) -> None:
        """EscalationThresholdResult supports equality comparison."""
        result1 = EscalationThresholdResult(
            threshold_reached=True,
            threshold_value=100,
            petition_type="CESSATION",
            current_count=100,
        )
        result2 = EscalationThresholdResult(
            threshold_reached=True,
            threshold_value=100,
            petition_type="CESSATION",
            current_count=100,
        )
        assert result1 == result2

    def test_inequality(self) -> None:
        """Different results are not equal."""
        result1 = EscalationThresholdResult(
            threshold_reached=True,
            threshold_value=100,
            petition_type="CESSATION",
            current_count=100,
        )
        result2 = EscalationThresholdResult(
            threshold_reached=False,
            threshold_value=100,
            petition_type="CESSATION",
            current_count=99,
        )
        assert result1 != result2


class TestCustomThresholds:
    """Test service with custom threshold configuration."""

    def test_custom_cessation_threshold(self) -> None:
        """Custom CESSATION threshold is used in checks."""
        service = EscalationThresholdService(cessation_threshold=200)

        # Below custom threshold
        result = service.check_threshold(PetitionType.CESSATION, 150)
        assert result.threshold_reached is False
        assert result.threshold_value == 200

        # At custom threshold
        result = service.check_threshold(PetitionType.CESSATION, 200)
        assert result.threshold_reached is True
        assert result.threshold_value == 200

    def test_custom_grievance_threshold(self) -> None:
        """Custom GRIEVANCE threshold is used in checks."""
        service = EscalationThresholdService(grievance_threshold=25)

        # Below custom threshold
        result = service.check_threshold(PetitionType.GRIEVANCE, 24)
        assert result.threshold_reached is False
        assert result.threshold_value == 25

        # At custom threshold
        result = service.check_threshold(PetitionType.GRIEVANCE, 25)
        assert result.threshold_reached is True
        assert result.threshold_value == 25
