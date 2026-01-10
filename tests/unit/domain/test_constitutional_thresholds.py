"""Unit tests for constitutional threshold definitions (Story 6.4, FR33).

Tests the threshold constants and registry defined in constitutional_thresholds.py.
"""

import pytest

from src.domain.errors.threshold import ThresholdNotFoundError
from src.domain.primitives.constitutional_thresholds import (
    ATTESTATION_PERIOD_THRESHOLD,
    CESSATION_BREACH_THRESHOLD,
    CESSATION_WINDOW_DAYS_THRESHOLD,
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
    ESCALATION_DAYS_THRESHOLD,
    FORK_SIGNAL_RATE_LIMIT_THRESHOLD,
    HALT_CONFIRMATION_SECONDS_THRESHOLD,
    MINIMUM_KEEPER_QUORUM_THRESHOLD,
    MISSED_ATTESTATIONS_THRESHOLD_DEF,
    OVERRIDE_GOVERNANCE_365_DAY_THRESHOLD,
    OVERRIDE_WARNING_30_DAY_THRESHOLD,
    RECOVERY_WAITING_HOURS_THRESHOLD,
    THRESHOLD_NAMES,
    TOPIC_DIVERSITY_THRESHOLD_DEF,
    WITNESS_POOL_MINIMUM_THRESHOLD,
    get_threshold,
    validate_all_thresholds,
)


class TestConstitutionalThresholdDefinitions:
    """Tests for the defined constitutional thresholds."""

    def test_all_thresholds_exist_in_registry(self) -> None:
        """Test all defined thresholds are in the registry (AC1)."""
        expected_names = {
            "cessation_breach_count",
            "cessation_window_days",
            "recovery_waiting_hours",
            "minimum_keeper_quorum",
            "escalation_days",
            "attestation_period_days",
            "missed_attestations_threshold",
            "override_warning_30_day",
            "override_governance_365_day",
            "topic_diversity_threshold",
            "fork_signal_rate_limit",
            "halt_confirmation_seconds",
            "witness_pool_minimum_high_stakes",
        }

        actual_names = set(THRESHOLD_NAMES)

        assert actual_names == expected_names

    def test_registry_contains_13_thresholds(self) -> None:
        """Test registry has all 13 constitutional thresholds."""
        assert len(CONSTITUTIONAL_THRESHOLD_REGISTRY) == 13

    def test_all_floors_are_correctly_defined(self) -> None:
        """Test all floors match their constitutional requirements."""
        assert CESSATION_BREACH_THRESHOLD.constitutional_floor == 10
        assert CESSATION_WINDOW_DAYS_THRESHOLD.constitutional_floor == 90
        assert RECOVERY_WAITING_HOURS_THRESHOLD.constitutional_floor == 48
        assert MINIMUM_KEEPER_QUORUM_THRESHOLD.constitutional_floor == 3
        assert ESCALATION_DAYS_THRESHOLD.constitutional_floor == 7
        assert ATTESTATION_PERIOD_THRESHOLD.constitutional_floor == 7
        assert MISSED_ATTESTATIONS_THRESHOLD_DEF.constitutional_floor == 2
        assert OVERRIDE_WARNING_30_DAY_THRESHOLD.constitutional_floor == 5
        assert OVERRIDE_GOVERNANCE_365_DAY_THRESHOLD.constitutional_floor == 20
        assert TOPIC_DIVERSITY_THRESHOLD_DEF.constitutional_floor == 0.30
        assert FORK_SIGNAL_RATE_LIMIT_THRESHOLD.constitutional_floor == 3
        assert HALT_CONFIRMATION_SECONDS_THRESHOLD.constitutional_floor == 5
        assert WITNESS_POOL_MINIMUM_THRESHOLD.constitutional_floor == 12

    def test_get_threshold_returns_correct_threshold(self) -> None:
        """Test get_threshold helper returns correct threshold."""
        threshold = get_threshold("cessation_breach_count")

        assert threshold.threshold_name == "cessation_breach_count"
        assert threshold.constitutional_floor == 10
        assert threshold.is_constitutional is True

    def test_get_threshold_raises_for_unknown(self) -> None:
        """Test get_threshold raises KeyError for unknown threshold."""
        with pytest.raises(KeyError):
            get_threshold("nonexistent_threshold")

    def test_validate_all_thresholds_passes(self) -> None:
        """Test validate_all_thresholds passes with default values."""
        # Should not raise
        validate_all_thresholds()

    def test_each_threshold_has_fr_reference(self) -> None:
        """Test each threshold has an FR/NFR/ADR reference in description."""
        for threshold in CONSTITUTIONAL_THRESHOLD_REGISTRY.thresholds:
            # Should have a reference like FR32, NFR39, ADR-3, RT-3
            assert threshold.fr_reference, f"{threshold.threshold_name} missing fr_reference"
            assert any(
                prefix in threshold.fr_reference
                for prefix in ["FR", "NFR", "ADR", "RT"]
            ), f"{threshold.threshold_name} has invalid fr_reference: {threshold.fr_reference}"

    def test_all_thresholds_are_constitutional(self) -> None:
        """Test all thresholds have is_constitutional=True (AC1)."""
        for threshold in CONSTITUTIONAL_THRESHOLD_REGISTRY.thresholds:
            assert threshold.is_constitutional is True, (
                f"{threshold.threshold_name} should be constitutional"
            )


class TestSpecificThresholds:
    """Tests for specific threshold requirements."""

    def test_cessation_threshold_fr32(self) -> None:
        """Test cessation threshold matches FR32 requirement."""
        threshold = get_threshold("cessation_breach_count")

        assert threshold.constitutional_floor == 10
        assert threshold.fr_reference == "FR32"
        assert "cessation" in threshold.description.lower()

    def test_cessation_window_fr32(self) -> None:
        """Test cessation window matches FR32 requirement (90 days)."""
        threshold = get_threshold("cessation_window_days")

        assert threshold.constitutional_floor == 90
        assert threshold.fr_reference == "FR32"

    def test_recovery_waiting_nfr41(self) -> None:
        """Test recovery waiting period matches NFR41 (48 hours)."""
        threshold = get_threshold("recovery_waiting_hours")

        assert threshold.constitutional_floor == 48
        assert threshold.fr_reference == "NFR41"

    def test_keeper_quorum_fr79(self) -> None:
        """Test keeper quorum matches FR79 (minimum 3)."""
        threshold = get_threshold("minimum_keeper_quorum")

        assert threshold.constitutional_floor == 3
        assert threshold.fr_reference == "FR79"

    def test_escalation_days_fr31(self) -> None:
        """Test escalation days matches FR31 (7 days)."""
        threshold = get_threshold("escalation_days")

        assert threshold.constitutional_floor == 7
        assert threshold.fr_reference == "FR31"

    def test_override_warning_fr27(self) -> None:
        """Test override warning threshold matches FR27."""
        threshold = get_threshold("override_warning_30_day")

        assert threshold.constitutional_floor == 5
        assert threshold.fr_reference == "FR27"

    def test_governance_review_rt3(self) -> None:
        """Test governance review threshold matches RT-3."""
        threshold = get_threshold("override_governance_365_day")

        assert threshold.constitutional_floor == 20
        assert threshold.fr_reference == "RT-3"

    def test_topic_diversity_fr73(self) -> None:
        """Test topic diversity threshold matches FR73 (30%)."""
        threshold = get_threshold("topic_diversity_threshold")

        assert threshold.constitutional_floor == 0.30
        assert threshold.fr_reference == "FR73"

    def test_halt_confirmation_adr3(self) -> None:
        """Test halt confirmation matches ADR-3 (5 seconds)."""
        threshold = get_threshold("halt_confirmation_seconds")

        assert threshold.constitutional_floor == 5
        assert threshold.fr_reference == "ADR-3"

    def test_witness_pool_fr59(self) -> None:
        """Test witness pool minimum matches FR59 (12 witnesses)."""
        threshold = get_threshold("witness_pool_minimum_high_stakes")

        assert threshold.constitutional_floor == 12
        assert threshold.fr_reference == "FR59"
