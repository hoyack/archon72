"""Unit tests for AcknowledgmentReasonCode domain model.

Story: 3.1 - Acknowledgment Reason Code Enumeration
FR-3.2: System SHALL require reason_code from enumerated values
FR-3.3: System SHALL require rationale for REFUSED and NO_ACTION_WARRANTED
FR-3.4: System SHALL require reference_petition_id for DUPLICATE
"""

from src.domain._compat import StrEnum
from uuid import uuid4

import pytest

from src.domain.models.acknowledgment_reason import (
    AcknowledgmentReasonCode,
    InvalidReasonCodeError,
    RationaleRequiredError,
    ReferenceRequiredError,
    validate_acknowledgment_requirements,
)


class TestAcknowledgmentReasonCodeEnum:
    """Tests for the AcknowledgmentReasonCode enumeration."""

    def test_all_reason_codes_exist(self) -> None:
        """Verify all required reason codes are defined per FR-3.2."""
        expected_codes = {
            "ADDRESSED",
            "NOTED",
            "DUPLICATE",
            "OUT_OF_SCOPE",
            "REFUSED",
            "NO_ACTION_WARRANTED",
            "WITHDRAWN",
            "EXPIRED",
            "KNIGHT_REFERRAL",
        }
        actual_codes = {code.value for code in AcknowledgmentReasonCode}
        assert actual_codes == expected_codes

    def test_enum_count(self) -> None:
        """Verify all reason codes are present."""
        assert len(AcknowledgmentReasonCode) == 9

    def test_enum_is_strenum(self) -> None:
        """Verify enum extends StrEnum for database compatibility."""
        assert issubclass(AcknowledgmentReasonCode, StrEnum)

    def test_enum_string_values(self) -> None:
        """Verify enum values match their names (StrEnum behavior)."""
        for code in AcknowledgmentReasonCode:
            assert code.value == code.name
            assert str(code) == code.value


class TestRequiresRationale:
    """Tests for rationale requirement validation per FR-3.3."""

    def test_requires_rationale_for_refused(self) -> None:
        """REFUSED requires rationale per FR-3.3."""
        assert AcknowledgmentReasonCode.requires_rationale(
            AcknowledgmentReasonCode.REFUSED
        )

    def test_requires_rationale_for_no_action_warranted(self) -> None:
        """NO_ACTION_WARRANTED requires rationale per FR-3.3."""
        assert AcknowledgmentReasonCode.requires_rationale(
            AcknowledgmentReasonCode.NO_ACTION_WARRANTED
        )

    @pytest.mark.parametrize(
        "code",
        [
            AcknowledgmentReasonCode.ADDRESSED,
            AcknowledgmentReasonCode.NOTED,
            AcknowledgmentReasonCode.DUPLICATE,
            AcknowledgmentReasonCode.OUT_OF_SCOPE,
            AcknowledgmentReasonCode.WITHDRAWN,
            AcknowledgmentReasonCode.EXPIRED,
            AcknowledgmentReasonCode.KNIGHT_REFERRAL,
        ],
    )
    def test_other_codes_do_not_require_rationale(
        self, code: AcknowledgmentReasonCode
    ) -> None:
        """Verify codes other than REFUSED/NO_ACTION_WARRANTED don't require rationale."""
        assert not AcknowledgmentReasonCode.requires_rationale(code)


class TestRequiresReference:
    """Tests for reference_petition_id requirement validation per FR-3.4."""

    def test_requires_reference_for_duplicate(self) -> None:
        """DUPLICATE requires reference_petition_id per FR-3.4."""
        assert AcknowledgmentReasonCode.requires_reference(
            AcknowledgmentReasonCode.DUPLICATE
        )

    @pytest.mark.parametrize(
        "code",
        [
            AcknowledgmentReasonCode.ADDRESSED,
            AcknowledgmentReasonCode.NOTED,
            AcknowledgmentReasonCode.OUT_OF_SCOPE,
            AcknowledgmentReasonCode.REFUSED,
            AcknowledgmentReasonCode.NO_ACTION_WARRANTED,
            AcknowledgmentReasonCode.WITHDRAWN,
            AcknowledgmentReasonCode.EXPIRED,
            AcknowledgmentReasonCode.KNIGHT_REFERRAL,
        ],
    )
    def test_other_codes_do_not_require_reference(
        self, code: AcknowledgmentReasonCode
    ) -> None:
        """Verify codes other than DUPLICATE don't require reference."""
        assert not AcknowledgmentReasonCode.requires_reference(code)


class TestFromString:
    """Tests for string-to-enum parsing."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("ADDRESSED", AcknowledgmentReasonCode.ADDRESSED),
            ("NOTED", AcknowledgmentReasonCode.NOTED),
            ("DUPLICATE", AcknowledgmentReasonCode.DUPLICATE),
            ("OUT_OF_SCOPE", AcknowledgmentReasonCode.OUT_OF_SCOPE),
            ("REFUSED", AcknowledgmentReasonCode.REFUSED),
            ("NO_ACTION_WARRANTED", AcknowledgmentReasonCode.NO_ACTION_WARRANTED),
            ("WITHDRAWN", AcknowledgmentReasonCode.WITHDRAWN),
            ("EXPIRED", AcknowledgmentReasonCode.EXPIRED),
        ],
    )
    def test_from_string_uppercase(
        self, input_str: str, expected: AcknowledgmentReasonCode
    ) -> None:
        """Valid uppercase strings are parsed correctly."""
        assert AcknowledgmentReasonCode.from_string(input_str) == expected

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("refused", AcknowledgmentReasonCode.REFUSED),
            ("Refused", AcknowledgmentReasonCode.REFUSED),
            ("duplicate", AcknowledgmentReasonCode.DUPLICATE),
            ("out_of_scope", AcknowledgmentReasonCode.OUT_OF_SCOPE),
            ("no_action_warranted", AcknowledgmentReasonCode.NO_ACTION_WARRANTED),
        ],
    )
    def test_case_insensitive_parsing(
        self, input_str: str, expected: AcknowledgmentReasonCode
    ) -> None:
        """Verify case-insensitive matching works."""
        assert AcknowledgmentReasonCode.from_string(input_str) == expected

    def test_from_string_with_whitespace(self) -> None:
        """Verify whitespace is trimmed."""
        assert (
            AcknowledgmentReasonCode.from_string("  REFUSED  ")
            == AcknowledgmentReasonCode.REFUSED
        )

    @pytest.mark.parametrize(
        "invalid_input",
        [
            "INVALID",
            "UNKNOWN",
            "REJECTED",  # Not a valid code
            "",
            "   ",
            "REFUSE",  # Typo
            "NO_ACTION",  # Incomplete
        ],
    )
    def test_invalid_code_raises_error(self, invalid_input: str) -> None:
        """Invalid strings raise InvalidReasonCodeError."""
        with pytest.raises(InvalidReasonCodeError) as exc_info:
            AcknowledgmentReasonCode.from_string(invalid_input)
        assert "Invalid reason code" in str(exc_info.value)
        assert "Valid codes are" in str(exc_info.value)


class TestValidateAcknowledgmentRequirements:
    """Tests for the validate_acknowledgment_requirements function."""

    def test_refused_with_rationale_passes(self) -> None:
        """REFUSED with rationale passes validation."""
        validate_acknowledgment_requirements(
            AcknowledgmentReasonCode.REFUSED,
            rationale="Petition violates content guidelines section 4.2",
        )

    def test_refused_without_rationale_raises(self) -> None:
        """REFUSED without rationale raises RationaleRequiredError."""
        with pytest.raises(RationaleRequiredError) as exc_info:
            validate_acknowledgment_requirements(
                AcknowledgmentReasonCode.REFUSED,
                rationale=None,
            )
        assert exc_info.value.reason_code == AcknowledgmentReasonCode.REFUSED
        assert "rationale is required" in str(exc_info.value).lower()

    def test_refused_with_empty_rationale_raises(self) -> None:
        """REFUSED with empty rationale raises RationaleRequiredError."""
        with pytest.raises(RationaleRequiredError):
            validate_acknowledgment_requirements(
                AcknowledgmentReasonCode.REFUSED,
                rationale="",
            )

    def test_refused_with_whitespace_only_rationale_raises(self) -> None:
        """REFUSED with whitespace-only rationale raises RationaleRequiredError."""
        with pytest.raises(RationaleRequiredError):
            validate_acknowledgment_requirements(
                AcknowledgmentReasonCode.REFUSED,
                rationale="   ",
            )

    def test_no_action_warranted_with_rationale_passes(self) -> None:
        """NO_ACTION_WARRANTED with rationale passes validation."""
        validate_acknowledgment_requirements(
            AcknowledgmentReasonCode.NO_ACTION_WARRANTED,
            rationale="After careful review, the concern is already addressed by existing policies",
        )

    def test_no_action_warranted_without_rationale_raises(self) -> None:
        """NO_ACTION_WARRANTED without rationale raises RationaleRequiredError."""
        with pytest.raises(RationaleRequiredError) as exc_info:
            validate_acknowledgment_requirements(
                AcknowledgmentReasonCode.NO_ACTION_WARRANTED,
                rationale=None,
            )
        assert (
            exc_info.value.reason_code == AcknowledgmentReasonCode.NO_ACTION_WARRANTED
        )

    def test_duplicate_with_reference_passes(self) -> None:
        """DUPLICATE with reference_petition_id passes validation."""
        reference_id = uuid4()
        validate_acknowledgment_requirements(
            AcknowledgmentReasonCode.DUPLICATE,
            reference_petition_id=reference_id,
        )

    def test_duplicate_without_reference_raises(self) -> None:
        """DUPLICATE without reference_petition_id raises ReferenceRequiredError."""
        with pytest.raises(ReferenceRequiredError) as exc_info:
            validate_acknowledgment_requirements(
                AcknowledgmentReasonCode.DUPLICATE,
                reference_petition_id=None,
            )
        assert "reference petition id is required" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "code",
        [
            AcknowledgmentReasonCode.ADDRESSED,
            AcknowledgmentReasonCode.NOTED,
            AcknowledgmentReasonCode.OUT_OF_SCOPE,
            AcknowledgmentReasonCode.WITHDRAWN,
            AcknowledgmentReasonCode.EXPIRED,
        ],
    )
    def test_codes_without_requirements_pass_with_no_extras(
        self, code: AcknowledgmentReasonCode
    ) -> None:
        """Codes without special requirements pass with minimal arguments."""
        validate_acknowledgment_requirements(code)

    @pytest.mark.parametrize(
        "code",
        [
            AcknowledgmentReasonCode.ADDRESSED,
            AcknowledgmentReasonCode.NOTED,
            AcknowledgmentReasonCode.OUT_OF_SCOPE,
            AcknowledgmentReasonCode.WITHDRAWN,
            AcknowledgmentReasonCode.EXPIRED,
        ],
    )
    def test_codes_without_requirements_accept_optional_rationale(
        self, code: AcknowledgmentReasonCode
    ) -> None:
        """Codes without rationale requirement can still accept optional rationale."""
        validate_acknowledgment_requirements(
            code, rationale="Optional additional context"
        )


class TestExceptionClasses:
    """Tests for custom exception classes."""

    def test_rationale_required_error_message(self) -> None:
        """RationaleRequiredError has informative message."""
        error = RationaleRequiredError(AcknowledgmentReasonCode.REFUSED)
        assert "REFUSED" in str(error)
        assert "FR-3.3" in str(error)
        assert error.reason_code == AcknowledgmentReasonCode.REFUSED

    def test_reference_required_error_message(self) -> None:
        """ReferenceRequiredError has informative message."""
        error = ReferenceRequiredError()
        assert "DUPLICATE" in str(error)
        assert "FR-3.4" in str(error)

    def test_invalid_reason_code_error_inheritance(self) -> None:
        """InvalidReasonCodeError is a ValueError."""
        assert issubclass(InvalidReasonCodeError, ValueError)

    def test_rationale_required_error_inheritance(self) -> None:
        """RationaleRequiredError is a ValueError."""
        assert issubclass(RationaleRequiredError, ValueError)

    def test_reference_required_error_inheritance(self) -> None:
        """ReferenceRequiredError is a ValueError."""
        assert issubclass(ReferenceRequiredError, ValueError)
