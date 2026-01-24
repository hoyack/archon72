"""Unit tests for PetitionSubmission domain model (Story 0.2, FR-2.2, Story 1.5).

Tests:
- Enum values present (PetitionType, PetitionState)
- Frozen dataclass behavior (immutability)
- with_state() creates new instance
- canonical_content_bytes() returns deterministic bytes
- Validation rejects text > 10,000 chars
- content_hash field accepts 32-byte values
- State machine transition matrix (FR-2.1, FR-2.3)
- Terminal state enforcement (FR-2.6)
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.state_transition import (
    InvalidStateTransitionError,
    PetitionAlreadyFatedError,
)
from src.domain.models.petition_submission import (
    STATE_TRANSITION_MATRIX,
    TERMINAL_STATES,
    PetitionState,
    PetitionSubmission,
    PetitionType,
)


class TestPetitionType:
    """Test PetitionType enum."""

    def test_all_values_present(self) -> None:
        """AC2: Verify all petition type values exist (FR-10.1, FR-10.4)."""
        assert PetitionType.GENERAL.value == "GENERAL"
        assert PetitionType.CESSATION.value == "CESSATION"
        assert PetitionType.GRIEVANCE.value == "GRIEVANCE"
        assert PetitionType.COLLABORATION.value == "COLLABORATION"
        assert PetitionType.META.value == "META"  # FR-10.4: META petitions

    def test_enum_count(self) -> None:
        """Verify exactly 5 petition types (including META, FR-10.4)."""
        assert len(PetitionType) == 5


class TestPetitionState:
    """Test PetitionState enum."""

    def test_all_values_present(self) -> None:
        """AC3: Verify all petition state values exist."""
        assert PetitionState.RECEIVED.value == "RECEIVED"
        assert PetitionState.DELIBERATING.value == "DELIBERATING"
        assert PetitionState.ACKNOWLEDGED.value == "ACKNOWLEDGED"
        assert PetitionState.REFERRED.value == "REFERRED"
        assert PetitionState.ESCALATED.value == "ESCALATED"

    def test_enum_count(self) -> None:
        """Verify exactly 5 petition states."""
        assert len(PetitionState) == 5


class TestPetitionSubmission:
    """Test PetitionSubmission domain model."""

    def test_create_basic_petition(self) -> None:
        """AC4: Can create a basic petition submission."""
        petition_id = uuid4()
        petition = PetitionSubmission(
            id=petition_id,
            type=PetitionType.GENERAL,
            text="Test petition content",
        )

        assert petition.id == petition_id
        assert petition.type == PetitionType.GENERAL
        assert petition.text == "Test petition content"
        assert petition.state == PetitionState.RECEIVED
        assert petition.submitter_id is None
        assert petition.content_hash is None
        assert petition.realm == "default"
        assert petition.created_at is not None
        assert petition.updated_at is not None

    def test_create_full_petition(self) -> None:
        """AC4: Can create petition with all fields."""
        petition_id = uuid4()
        submitter_id = uuid4()
        content_hash = b"0" * 32
        created_at = datetime.now(timezone.utc)

        petition = PetitionSubmission(
            id=petition_id,
            type=PetitionType.CESSATION,
            text="Full petition content",
            state=PetitionState.DELIBERATING,
            submitter_id=submitter_id,
            content_hash=content_hash,
            realm="test-realm",
            created_at=created_at,
            updated_at=created_at,
        )

        assert petition.id == petition_id
        assert petition.type == PetitionType.CESSATION
        assert petition.state == PetitionState.DELIBERATING
        assert petition.submitter_id == submitter_id
        assert petition.content_hash == content_hash
        assert petition.realm == "test-realm"

    def test_frozen_dataclass_immutable(self) -> None:
        """AC5: Verify frozen dataclass is immutable."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
        )

        with pytest.raises(AttributeError):
            petition.state = PetitionState.DELIBERATING  # type: ignore[misc]

        with pytest.raises(AttributeError):
            petition.text = "Modified content"  # type: ignore[misc]

    def test_with_state_creates_new_instance(self) -> None:
        """AC5: with_state() creates new instance with updated state."""
        original = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.RECEIVED,
        )

        updated = original.with_state(PetitionState.DELIBERATING)

        # Original unchanged
        assert original.state == PetitionState.RECEIVED
        # New instance has updated state
        assert updated.state == PetitionState.DELIBERATING
        # Same identity
        assert updated.id == original.id
        assert updated.type == original.type
        assert updated.text == original.text
        # Different instances
        assert original is not updated

    def test_with_state_updates_timestamp(self) -> None:
        """AC5: with_state() updates the updated_at timestamp."""
        original = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
        )
        original_updated_at = original.updated_at

        updated = original.with_state(PetitionState.DELIBERATING)

        # updated_at should be >= original
        assert updated.updated_at >= original_updated_at
        # created_at should be preserved
        assert updated.created_at == original.created_at

    def test_canonical_content_bytes_deterministic(self) -> None:
        """AC5: canonical_content_bytes() returns deterministic UTF-8 bytes."""
        text = "Test petition with unicode: \u00e9\u00e8\u00ea"
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text=text,
        )

        # Should return same bytes every time
        bytes1 = petition.canonical_content_bytes()
        bytes2 = petition.canonical_content_bytes()

        assert bytes1 == bytes2
        assert bytes1 == text.encode("utf-8")

    def test_validation_rejects_oversized_text(self) -> None:
        """AC5: Validation rejects text > 10,000 chars."""
        oversized_text = "x" * 10_001

        with pytest.raises(ValueError, match="exceeds maximum length"):
            PetitionSubmission(
                id=uuid4(),
                type=PetitionType.GENERAL,
                text=oversized_text,
            )

    def test_validation_accepts_max_length_text(self) -> None:
        """AC5: Validation accepts text exactly at max length."""
        max_text = "x" * 10_000

        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text=max_text,
        )

        assert len(petition.text) == 10_000

    def test_content_hash_accepts_32_bytes(self) -> None:
        """AC6: content_hash field accepts 32-byte values."""
        valid_hash = b"0" * 32

        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            content_hash=valid_hash,
        )

        assert petition.content_hash == valid_hash
        assert len(petition.content_hash) == 32

    def test_content_hash_rejects_invalid_length(self) -> None:
        """AC6: content_hash rejects non-32-byte values."""
        invalid_hash_short = b"0" * 31
        invalid_hash_long = b"0" * 33

        with pytest.raises(ValueError, match="32 bytes"):
            PetitionSubmission(
                id=uuid4(),
                type=PetitionType.GENERAL,
                text="Test content",
                content_hash=invalid_hash_short,
            )

        with pytest.raises(ValueError, match="32 bytes"):
            PetitionSubmission(
                id=uuid4(),
                type=PetitionType.GENERAL,
                text="Test content",
                content_hash=invalid_hash_long,
            )

    def test_content_hash_none_allowed(self) -> None:
        """AC6: content_hash can be None (deferred to Story 0.5)."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            content_hash=None,
        )

        assert petition.content_hash is None

    def test_with_content_hash_creates_new_instance(self) -> None:
        """with_content_hash() creates new instance with hash set."""
        original = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
        )
        new_hash = b"1" * 32

        updated = original.with_content_hash(new_hash)

        # Original unchanged
        assert original.content_hash is None
        # New instance has hash
        assert updated.content_hash == new_hash
        # Same identity
        assert updated.id == original.id
        # Different instances
        assert original is not updated

    def test_equality_based_on_fields(self) -> None:
        """Verify equality is based on field values."""
        petition_id = uuid4()
        created_at = datetime.now(timezone.utc)

        petition1 = PetitionSubmission(
            id=petition_id,
            type=PetitionType.GENERAL,
            text="Test content",
            created_at=created_at,
            updated_at=created_at,
        )
        petition2 = PetitionSubmission(
            id=petition_id,
            type=PetitionType.GENERAL,
            text="Test content",
            created_at=created_at,
            updated_at=created_at,
        )

        assert petition1 == petition2
        assert hash(petition1) == hash(petition2)

    def test_all_petition_types_can_be_created(self) -> None:
        """Verify all petition types work in creation."""
        for petition_type in PetitionType:
            petition = PetitionSubmission(
                id=uuid4(),
                type=petition_type,
                text="Test content",
            )
            assert petition.type == petition_type

    def test_valid_state_transitions_from_received(self) -> None:
        """FR-2.1, FR-5.1: RECEIVED can transition to DELIBERATING, ACKNOWLEDGED, or ESCALATED."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.RECEIVED,
        )

        # Valid: RECEIVED -> DELIBERATING
        deliberating = petition.with_state(PetitionState.DELIBERATING)
        assert deliberating.state == PetitionState.DELIBERATING

        # Valid: RECEIVED -> ACKNOWLEDGED (withdrawal)
        acknowledged = petition.with_state(PetitionState.ACKNOWLEDGED)
        assert acknowledged.state == PetitionState.ACKNOWLEDGED

        # Valid: RECEIVED -> ESCALATED (auto-escalation, FR-5.1)
        escalated = petition.with_state(PetitionState.ESCALATED)
        assert escalated.state == PetitionState.ESCALATED

    def test_valid_state_transitions_from_deliberating(self) -> None:
        """FR-2.1: DELIBERATING can transition to any terminal fate."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.DELIBERATING,
        )

        # Valid: DELIBERATING -> ACKNOWLEDGED
        ack = petition.with_state(PetitionState.ACKNOWLEDGED)
        assert ack.state == PetitionState.ACKNOWLEDGED

        # Valid: DELIBERATING -> REFERRED
        referred = petition.with_state(PetitionState.REFERRED)
        assert referred.state == PetitionState.REFERRED

        # Valid: DELIBERATING -> ESCALATED
        escalated = petition.with_state(PetitionState.ESCALATED)
        assert escalated.state == PetitionState.ESCALATED

        # Valid: DELIBERATING -> DEFERRED
        deferred = petition.with_state(PetitionState.DEFERRED)
        assert deferred.state == PetitionState.DEFERRED

        # Valid: DELIBERATING -> NO_RESPONSE
        no_response = petition.with_state(PetitionState.NO_RESPONSE)
        assert no_response.state == PetitionState.NO_RESPONSE


class TestPetitionStateMachine:
    """Test PetitionState state machine (Story 1.5, FR-2.1, FR-2.3, FR-2.6)."""

    def test_terminal_states_defined(self) -> None:
        """FR-2.6: Terminal states are the terminal fates."""
        assert PetitionState.ACKNOWLEDGED in TERMINAL_STATES
        assert PetitionState.REFERRED in TERMINAL_STATES
        assert PetitionState.ESCALATED in TERMINAL_STATES
        assert PetitionState.DEFERRED in TERMINAL_STATES
        assert PetitionState.NO_RESPONSE in TERMINAL_STATES
        assert PetitionState.RECEIVED not in TERMINAL_STATES
        assert PetitionState.DELIBERATING not in TERMINAL_STATES
        assert len(TERMINAL_STATES) == 5

    def test_is_terminal_method(self) -> None:
        """FR-2.6: is_terminal() correctly identifies terminal states."""
        assert PetitionState.ACKNOWLEDGED.is_terminal() is True
        assert PetitionState.REFERRED.is_terminal() is True
        assert PetitionState.ESCALATED.is_terminal() is True
        assert PetitionState.DEFERRED.is_terminal() is True
        assert PetitionState.NO_RESPONSE.is_terminal() is True
        assert PetitionState.RECEIVED.is_terminal() is False
        assert PetitionState.DELIBERATING.is_terminal() is False

    def test_valid_transitions_from_received(self) -> None:
        """FR-2.3, FR-5.1: RECEIVED has defined valid transitions."""
        valid = PetitionState.RECEIVED.valid_transitions()
        assert PetitionState.DELIBERATING in valid
        assert PetitionState.ACKNOWLEDGED in valid
        assert PetitionState.ESCALATED in valid  # FR-5.1: auto-escalation path
        assert PetitionState.REFERRED not in valid
        assert PetitionState.RECEIVED not in valid

    def test_valid_transitions_from_deliberating(self) -> None:
        """FR-2.3: DELIBERATING can reach any terminal fate."""
        valid = PetitionState.DELIBERATING.valid_transitions()
        assert PetitionState.ACKNOWLEDGED in valid
        assert PetitionState.REFERRED in valid
        assert PetitionState.ESCALATED in valid
        assert PetitionState.DEFERRED in valid
        assert PetitionState.NO_RESPONSE in valid
        assert PetitionState.RECEIVED not in valid
        assert PetitionState.DELIBERATING not in valid

    def test_terminal_states_have_no_transitions(self) -> None:
        """FR-2.6: Terminal states have no valid transitions."""
        for state in TERMINAL_STATES:
            assert state.valid_transitions() == frozenset()

    def test_transition_matrix_complete(self) -> None:
        """FR-2.3: Transition matrix covers all states."""
        for state in PetitionState:
            assert state in STATE_TRANSITION_MATRIX

    def test_invalid_transition_received_to_referred_raises(self) -> None:
        """FR-2.3: RECEIVED -> REFERRED is invalid."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.RECEIVED,
        )

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            petition.with_state(PetitionState.REFERRED)

        assert exc_info.value.from_state == PetitionState.RECEIVED
        assert exc_info.value.to_state == PetitionState.REFERRED
        assert PetitionState.DELIBERATING in exc_info.value.allowed_transitions
        assert PetitionState.ACKNOWLEDGED in exc_info.value.allowed_transitions

    def test_valid_transition_received_to_escalated_for_auto_escalation(self) -> None:
        """FR-5.1: RECEIVED -> ESCALATED is valid for auto-escalation.

        Constitutional: CT-14 "Silence must be expensive" - petitions with
        sufficient collective support (co-signer threshold) bypass deliberation
        to reach King attention directly.
        """
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.RECEIVED,
        )

        escalated = petition.with_state(PetitionState.ESCALATED)

        assert escalated.state == PetitionState.ESCALATED
        assert escalated.state.is_terminal()

    def test_invalid_transition_received_to_received_raises(self) -> None:
        """FR-2.3: RECEIVED -> RECEIVED (self-loop) is invalid."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.RECEIVED,
        )

        with pytest.raises(InvalidStateTransitionError):
            petition.with_state(PetitionState.RECEIVED)

    def test_invalid_transition_deliberating_to_received_raises(self) -> None:
        """FR-2.3: DELIBERATING -> RECEIVED (backwards) is invalid."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.DELIBERATING,
        )

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            petition.with_state(PetitionState.RECEIVED)

        assert exc_info.value.from_state == PetitionState.DELIBERATING
        assert exc_info.value.to_state == PetitionState.RECEIVED

    def test_invalid_transition_deliberating_to_deliberating_raises(self) -> None:
        """FR-2.3: DELIBERATING -> DELIBERATING (self-loop) is invalid."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.DELIBERATING,
        )

        with pytest.raises(InvalidStateTransitionError):
            petition.with_state(PetitionState.DELIBERATING)


class TestPetitionAlreadyFated:
    """Test terminal state enforcement (Story 1.5, FR-2.6)."""

    def test_acknowledged_cannot_transition(self) -> None:
        """FR-2.6: ACKNOWLEDGED is terminal, no transitions allowed."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.ACKNOWLEDGED,
        )

        for target_state in PetitionState:
            with pytest.raises(PetitionAlreadyFatedError) as exc_info:
                petition.with_state(target_state)

            assert exc_info.value.terminal_state == PetitionState.ACKNOWLEDGED
            assert str(petition.id) in str(exc_info.value)

    def test_referred_cannot_transition(self) -> None:
        """FR-2.6: REFERRED is terminal, no transitions allowed."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.REFERRED,
        )

        for target_state in PetitionState:
            with pytest.raises(PetitionAlreadyFatedError) as exc_info:
                petition.with_state(target_state)

            assert exc_info.value.terminal_state == PetitionState.REFERRED

    def test_escalated_cannot_transition(self) -> None:
        """FR-2.6: ESCALATED is terminal, no transitions allowed."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.ESCALATED,
        )

        for target_state in PetitionState:
            with pytest.raises(PetitionAlreadyFatedError) as exc_info:
                petition.with_state(target_state)

            assert exc_info.value.terminal_state == PetitionState.ESCALATED

    def test_petition_already_fated_error_message(self) -> None:
        """PetitionAlreadyFatedError includes petition_id and state."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.ACKNOWLEDGED,
        )

        with pytest.raises(PetitionAlreadyFatedError) as exc_info:
            petition.with_state(PetitionState.DELIBERATING)

        error = exc_info.value
        assert error.petition_id == str(petition.id)
        assert error.terminal_state == PetitionState.ACKNOWLEDGED
        assert "ACKNOWLEDGED" in str(error)
        assert "Terminal states cannot be modified" in str(error)


class TestInvalidStateTransitionError:
    """Test InvalidStateTransitionError attributes (Story 1.5, FR-2.3)."""

    def test_error_includes_allowed_transitions(self) -> None:
        """InvalidStateTransitionError lists valid transitions."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.RECEIVED,
        )

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            petition.with_state(PetitionState.REFERRED)

        error = exc_info.value
        assert (
            len(error.allowed_transitions) == 3
        )  # DELIBERATING, ACKNOWLEDGED, ESCALATED
        assert PetitionState.DELIBERATING in error.allowed_transitions
        assert PetitionState.ACKNOWLEDGED in error.allowed_transitions
        assert PetitionState.ESCALATED in error.allowed_transitions

    def test_error_message_format(self) -> None:
        """InvalidStateTransitionError has descriptive message."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test content",
            state=PetitionState.RECEIVED,
        )

        # RECEIVED -> REFERRED is invalid (REFERRED only from DELIBERATING)
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            petition.with_state(PetitionState.REFERRED)

        error_msg = str(exc_info.value)
        assert "RECEIVED" in error_msg
        assert "REFERRED" in error_msg
        assert "Invalid state transition" in error_msg


class TestCompleteStateTransitionCoverage:
    """Comprehensive state transition coverage (Story 1.5)."""

    def test_all_valid_transitions_work(self) -> None:
        """All transitions in the matrix succeed."""
        for from_state, valid_targets in STATE_TRANSITION_MATRIX.items():
            if not valid_targets:  # Skip terminal states
                continue

            for to_state in valid_targets:
                petition = PetitionSubmission(
                    id=uuid4(),
                    type=PetitionType.GENERAL,
                    text="Test content",
                    state=from_state,
                )
                updated = petition.with_state(to_state)
                assert updated.state == to_state

    def test_all_invalid_transitions_raise(self) -> None:
        """All transitions NOT in the matrix raise errors."""
        all_states = set(PetitionState)

        for from_state, valid_targets in STATE_TRANSITION_MATRIX.items():
            invalid_targets = all_states - valid_targets

            for to_state in invalid_targets:
                petition = PetitionSubmission(
                    id=uuid4(),
                    type=PetitionType.GENERAL,
                    text="Test content",
                    state=from_state,
                )

                # Terminal states raise PetitionAlreadyFatedError
                # Non-terminal states raise InvalidStateTransitionError
                if from_state.is_terminal():
                    with pytest.raises(PetitionAlreadyFatedError):
                        petition.with_state(to_state)
                else:
                    with pytest.raises(InvalidStateTransitionError):
                        petition.with_state(to_state)

    def test_happy_path_received_to_deliberating_to_acknowledged(self) -> None:
        """Happy path: petition goes through normal lifecycle."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition for acknowledgment",
            state=PetitionState.RECEIVED,
        )

        # Step 1: Move to deliberation
        deliberating = petition.with_state(PetitionState.DELIBERATING)
        assert deliberating.state == PetitionState.DELIBERATING

        # Step 2: Three Fates acknowledge
        acknowledged = deliberating.with_state(PetitionState.ACKNOWLEDGED)
        assert acknowledged.state == PetitionState.ACKNOWLEDGED
        assert acknowledged.state.is_terminal()

        # Step 3: Cannot modify further
        with pytest.raises(PetitionAlreadyFatedError):
            acknowledged.with_state(PetitionState.REFERRED)

    def test_happy_path_received_to_deliberating_to_referred(self) -> None:
        """Happy path: petition referred to Knight."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition for referral",
            state=PetitionState.RECEIVED,
        )

        deliberating = petition.with_state(PetitionState.DELIBERATING)
        referred = deliberating.with_state(PetitionState.REFERRED)

        assert referred.state == PetitionState.REFERRED
        assert referred.state.is_terminal()

    def test_happy_path_received_to_deliberating_to_escalated(self) -> None:
        """Happy path: petition escalated to King."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition for escalation",
            state=PetitionState.RECEIVED,
        )

        deliberating = petition.with_state(PetitionState.DELIBERATING)
        escalated = deliberating.with_state(PetitionState.ESCALATED)

        assert escalated.state == PetitionState.ESCALATED
        assert escalated.state.is_terminal()

    def test_withdrawal_path_received_to_acknowledged(self) -> None:
        """Withdrawal path: petition acknowledged before deliberation."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition withdrawn",
            state=PetitionState.RECEIVED,
        )

        # Direct withdrawal bypasses deliberation
        acknowledged = petition.with_state(PetitionState.ACKNOWLEDGED)

        assert acknowledged.state == PetitionState.ACKNOWLEDGED
        assert acknowledged.state.is_terminal()

    def test_auto_escalation_path_received_to_escalated(self) -> None:
        """Auto-escalation path: petition escalated directly from RECEIVED (FR-5.1).

        Constitutional: CT-14 "Silence must be expensive" - petitions with
        sufficient collective support (co-signer threshold reached) bypass
        deliberation to reach King attention directly.
        """
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.CESSATION,
            text="Test petition for auto-escalation",
            state=PetitionState.RECEIVED,
        )

        # Direct escalation bypasses deliberation (when threshold reached)
        escalated = petition.with_state(
            PetitionState.ESCALATED,
            reason="Auto-escalated: co-signer threshold (100) reached",
        )

        assert escalated.state == PetitionState.ESCALATED
        assert escalated.state.is_terminal()
        assert (
            escalated.fate_reason == "Auto-escalated: co-signer threshold (100) reached"
        )

        # Cannot modify further
        with pytest.raises(PetitionAlreadyFatedError):
            escalated.with_state(PetitionState.ACKNOWLEDGED)
