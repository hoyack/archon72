"""Unit tests for LegitimacyStateRecord projection model.

Tests cover acceptance criteria for story consent-gov-1.5:
- AC4: Domain models for each projection record type
- Validation of legitimacy band transitions
"""

from datetime import datetime, timezone

import pytest

from src.domain.governance.projections.legitimacy_state import LegitimacyStateRecord


class TestLegitimacyStateRecordCreation:
    """Tests for LegitimacyStateRecord creation and validation."""

    def test_valid_legitimacy_state_creation(self) -> None:
        """LegitimacyStateRecord with valid data creates successfully."""
        now = datetime.now(timezone.utc)
        record = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="full",
            band_entered_at=now,
            violation_count=0,
            last_violation_at=None,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        assert record.entity_id == "archon-42"
        assert record.entity_type == "archon"
        assert record.current_band == "full"
        assert record.violation_count == 0
        assert record.last_violation_at is None

    def test_legitimacy_state_record_is_immutable(self) -> None:
        """LegitimacyStateRecord fields cannot be modified after creation."""
        now = datetime.now(timezone.utc)
        record = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="full",
            band_entered_at=now,
            violation_count=0,
            last_violation_at=None,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        with pytest.raises(AttributeError):
            record.current_band = "suspended"  # type: ignore[misc]

    def test_invalid_band_raises_error(self) -> None:
        """Invalid current_band raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            LegitimacyStateRecord(
                entity_id="archon-42",
                entity_type="archon",
                current_band="invalid_band",
                band_entered_at=now,
                violation_count=0,
                last_violation_at=None,
                last_restoration_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
        assert "Invalid legitimacy band" in str(exc_info.value)

    def test_negative_violation_count_raises_error(self) -> None:
        """Negative violation_count raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            LegitimacyStateRecord(
                entity_id="archon-42",
                entity_type="archon",
                current_band="full",
                band_entered_at=now,
                violation_count=-1,
                last_violation_at=None,
                last_restoration_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
        assert "non-negative" in str(exc_info.value)


class TestLegitimacyStateRecordValidBands:
    """Tests for valid bands enumeration."""

    def test_all_valid_bands_can_be_created(self) -> None:
        """All VALID_BANDS can be used to create records."""
        now = datetime.now(timezone.utc)
        for band in LegitimacyStateRecord.VALID_BANDS:
            record = LegitimacyStateRecord(
                entity_id="archon-42",
                entity_type="archon",
                current_band=band,
                band_entered_at=now,
                violation_count=0,
                last_violation_at=None,
                last_restoration_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
            assert record.current_band == band

    def test_valid_bands_contains_expected_values(self) -> None:
        """VALID_BANDS contains all expected legitimacy bands."""
        expected = {"full", "provisional", "suspended"}
        assert LegitimacyStateRecord.VALID_BANDS == frozenset(expected)


class TestLegitimacyStateRecordTransitions:
    """Tests for band transition logic."""

    def test_full_can_decay_to_provisional(self) -> None:
        """Full band can decay to provisional."""
        now = datetime.now(timezone.utc)
        record = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="full",
            band_entered_at=now,
            violation_count=0,
            last_violation_at=None,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        assert record.can_decay()
        assert record.get_decay_band() == "provisional"

    def test_provisional_can_decay_to_suspended(self) -> None:
        """Provisional band can decay to suspended."""
        now = datetime.now(timezone.utc)
        record = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="provisional",
            band_entered_at=now,
            violation_count=1,
            last_violation_at=now,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        assert record.can_decay()
        assert record.get_decay_band() == "suspended"

    def test_suspended_cannot_decay_further(self) -> None:
        """Suspended band cannot decay further."""
        now = datetime.now(timezone.utc)
        record = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="suspended",
            band_entered_at=now,
            violation_count=2,
            last_violation_at=now,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        assert not record.can_decay()
        # get_decay_band() returns same band when at bottom
        assert record.get_decay_band() == "suspended"

    def test_suspended_can_restore_to_provisional(self) -> None:
        """Suspended band can restore to provisional."""
        now = datetime.now(timezone.utc)
        record = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="suspended",
            band_entered_at=now,
            violation_count=2,
            last_violation_at=now,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        assert record.can_restore()
        assert record.get_restoration_band() == "provisional"

    def test_provisional_can_restore_to_full(self) -> None:
        """Provisional band can restore to full."""
        now = datetime.now(timezone.utc)
        record = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="provisional",
            band_entered_at=now,
            violation_count=1,
            last_violation_at=now,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        assert record.can_restore()
        assert record.get_restoration_band() == "full"

    def test_full_cannot_restore_further(self) -> None:
        """Full band cannot restore further."""
        now = datetime.now(timezone.utc)
        record = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="full",
            band_entered_at=now,
            violation_count=0,
            last_violation_at=None,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        assert not record.can_restore()
        # get_restoration_band() returns same band when at top
        assert record.get_restoration_band() == "full"


class TestLegitimacyStateRecordHelpers:
    """Tests for helper methods."""

    def test_is_suspended_for_suspended_band(self) -> None:
        """is_suspended returns True for suspended band."""
        now = datetime.now(timezone.utc)
        record = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="suspended",
            band_entered_at=now,
            violation_count=2,
            last_violation_at=now,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert record.is_suspended()

    def test_is_suspended_for_non_suspended_bands(self) -> None:
        """is_suspended returns False for non-suspended bands."""
        now = datetime.now(timezone.utc)
        for band in ["full", "provisional"]:
            record = LegitimacyStateRecord(
                entity_id="archon-42",
                entity_type="archon",
                current_band=band,
                band_entered_at=now,
                violation_count=0,
                last_violation_at=None,
                last_restoration_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
            assert not record.is_suspended()

    def test_has_full_legitimacy(self) -> None:
        """has_full_legitimacy returns True only for full band."""
        now = datetime.now(timezone.utc)
        record_full = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="full",
            band_entered_at=now,
            violation_count=0,
            last_violation_at=None,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert record_full.has_full_legitimacy()

        record_provisional = LegitimacyStateRecord(
            entity_id="archon-42",
            entity_type="archon",
            current_band="provisional",
            band_entered_at=now,
            violation_count=1,
            last_violation_at=now,
            last_restoration_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert not record_provisional.has_full_legitimacy()
