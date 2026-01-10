"""Unit tests for KeyGenerationCeremony domain model (FR69, ADR-4).

Tests the ceremony domain model, state machine, and validation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.models.ceremony_witness import CeremonyWitness, WitnessType
from src.domain.models.key_generation_ceremony import (
    CEREMONY_TIMEOUT_SECONDS,
    REQUIRED_WITNESSES,
    TRANSITION_PERIOD_DAYS,
    VALID_TRANSITIONS,
    CeremonyState,
    CeremonyType,
    KeyGenerationCeremony,
)


class TestKeyGenerationCeremonyCreation:
    """Tests for KeyGenerationCeremony creation."""

    def test_create_valid_new_key_ceremony(self) -> None:
        """Create a valid new key ceremony."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        assert ceremony.keeper_id == "KEEPER:alice"
        assert ceremony.ceremony_type == CeremonyType.NEW_KEEPER_KEY
        assert ceremony.state == CeremonyState.PENDING
        assert ceremony.witnesses == []
        assert ceremony.new_key_id is None
        assert ceremony.old_key_id is None

    def test_create_valid_rotation_ceremony(self) -> None:
        """Create a valid key rotation ceremony."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:bob",
            ceremony_type=CeremonyType.KEY_ROTATION,
            old_key_id="old-key-123",
        )

        assert ceremony.ceremony_type == CeremonyType.KEY_ROTATION
        assert ceremony.old_key_id == "old-key-123"

    def test_create_with_invalid_id_type_raises(self) -> None:
        """FR69: Invalid ID type raises ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeyGenerationCeremony(
                id="not-a-uuid",  # type: ignore
                keeper_id="KEEPER:alice",
                ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            )

        assert "FR69" in str(exc_info.value)
        assert "UUID" in str(exc_info.value)

    def test_create_with_empty_keeper_id_raises(self) -> None:
        """FR69: Empty keeper_id raises ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeyGenerationCeremony(
                id=uuid4(),
                keeper_id="",
                ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            )

        assert "FR69" in str(exc_info.value)
        assert "keeper_id" in str(exc_info.value)

    def test_create_with_invalid_ceremony_type_raises(self) -> None:
        """FR69: Invalid ceremony_type raises ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeyGenerationCeremony(
                id=uuid4(),
                keeper_id="KEEPER:alice",
                ceremony_type="invalid",  # type: ignore
            )

        assert "FR69" in str(exc_info.value)
        assert "ceremony_type" in str(exc_info.value)

    def test_create_with_invalid_state_raises(self) -> None:
        """FR69: Invalid state raises ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeyGenerationCeremony(
                id=uuid4(),
                keeper_id="KEEPER:alice",
                ceremony_type=CeremonyType.NEW_KEEPER_KEY,
                state="invalid",  # type: ignore
            )

        assert "FR69" in str(exc_info.value)
        assert "state" in str(exc_info.value)


class TestCeremonyStateTransitions:
    """Tests for ceremony state machine (FP-4)."""

    def test_pending_can_transition_to_approved(self) -> None:
        """FP-4: PENDING can transition to APPROVED."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        assert ceremony.can_transition_to(CeremonyState.APPROVED)

    def test_pending_can_transition_to_failed(self) -> None:
        """FP-4: PENDING can transition to FAILED."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        assert ceremony.can_transition_to(CeremonyState.FAILED)

    def test_pending_can_transition_to_expired(self) -> None:
        """FP-4: PENDING can transition to EXPIRED."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        assert ceremony.can_transition_to(CeremonyState.EXPIRED)

    def test_pending_cannot_transition_to_executing(self) -> None:
        """FP-4: PENDING cannot transition directly to EXECUTING."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        assert not ceremony.can_transition_to(CeremonyState.EXECUTING)

    def test_pending_cannot_transition_to_completed(self) -> None:
        """FP-4: PENDING cannot transition directly to COMPLETED."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        assert not ceremony.can_transition_to(CeremonyState.COMPLETED)

    def test_approved_can_transition_to_executing(self) -> None:
        """FP-4: APPROVED can transition to EXECUTING."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.APPROVED,
        )

        assert ceremony.can_transition_to(CeremonyState.EXECUTING)

    def test_approved_can_transition_to_expired(self) -> None:
        """FP-4: APPROVED can transition to EXPIRED."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.APPROVED,
        )

        assert ceremony.can_transition_to(CeremonyState.EXPIRED)

    def test_executing_can_transition_to_completed(self) -> None:
        """FP-4: EXECUTING can transition to COMPLETED."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.EXECUTING,
        )

        assert ceremony.can_transition_to(CeremonyState.COMPLETED)

    def test_executing_can_transition_to_failed(self) -> None:
        """FP-4: EXECUTING can transition to FAILED."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.EXECUTING,
        )

        assert ceremony.can_transition_to(CeremonyState.FAILED)

    def test_terminal_states_cannot_transition(self) -> None:
        """FP-4: Terminal states cannot transition to any other state."""
        for terminal_state in [
            CeremonyState.COMPLETED,
            CeremonyState.FAILED,
            CeremonyState.EXPIRED,
        ]:
            ceremony = KeyGenerationCeremony(
                id=uuid4(),
                keeper_id="KEEPER:alice",
                ceremony_type=CeremonyType.NEW_KEEPER_KEY,
                state=terminal_state,
            )

            for target_state in CeremonyState:
                assert not ceremony.can_transition_to(target_state)

    def test_transition_to_updates_state(self) -> None:
        """FP-4: transition_to() updates state when valid."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        ceremony.transition_to(CeremonyState.APPROVED)

        assert ceremony.state == CeremonyState.APPROVED

    def test_transition_to_invalid_state_raises(self) -> None:
        """FP-4: Invalid state transition raises ConstitutionalViolationError."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            ceremony.transition_to(CeremonyState.COMPLETED)

        assert "FP-4" in str(exc_info.value)
        assert "pending" in str(exc_info.value).lower()
        assert "completed" in str(exc_info.value).lower()


class TestCeremonyStateHelpers:
    """Tests for ceremony state helper methods."""

    def test_is_terminal_completed(self) -> None:
        """COMPLETED is terminal state."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.COMPLETED,
        )

        assert ceremony.is_terminal()

    def test_is_terminal_failed(self) -> None:
        """FAILED is terminal state."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.FAILED,
        )

        assert ceremony.is_terminal()

    def test_is_terminal_expired(self) -> None:
        """EXPIRED is terminal state."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.EXPIRED,
        )

        assert ceremony.is_terminal()

    def test_is_active_pending(self) -> None:
        """PENDING is active state."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.PENDING,
        )

        assert ceremony.is_active()
        assert not ceremony.is_terminal()

    def test_is_active_approved(self) -> None:
        """APPROVED is active state."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.APPROVED,
        )

        assert ceremony.is_active()

    def test_is_active_executing(self) -> None:
        """EXECUTING is active state."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.EXECUTING,
        )

        assert ceremony.is_active()


class TestCeremonyWitnesses:
    """Tests for ceremony witness tracking (CT-12)."""

    def test_has_sufficient_witnesses_with_zero(self) -> None:
        """CT-12: No witnesses is insufficient."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        assert not ceremony.has_sufficient_witnesses()

    def test_has_sufficient_witnesses_below_threshold(self) -> None:
        """CT-12: Below threshold is insufficient."""
        witnesses = [
            CeremonyWitness(
                witness_id="KEEPER:witness1",
                signature=b"sig1",
                witness_type=WitnessType.KEEPER,
            ),
            CeremonyWitness(
                witness_id="KEEPER:witness2",
                signature=b"sig2",
                witness_type=WitnessType.KEEPER,
            ),
        ]

        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            witnesses=witnesses,
        )

        assert len(ceremony.witnesses) == 2
        assert not ceremony.has_sufficient_witnesses()

    def test_has_sufficient_witnesses_at_threshold(self) -> None:
        """CT-12: At threshold is sufficient."""
        witnesses = [
            CeremonyWitness(
                witness_id=f"KEEPER:witness{i}",
                signature=f"sig{i}".encode(),
                witness_type=WitnessType.KEEPER,
            )
            for i in range(REQUIRED_WITNESSES)
        ]

        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            witnesses=witnesses,
        )

        assert len(ceremony.witnesses) == REQUIRED_WITNESSES
        assert ceremony.has_sufficient_witnesses()

    def test_get_witness_ids(self) -> None:
        """Get list of witness IDs."""
        witnesses = [
            CeremonyWitness(
                witness_id="KEEPER:alice",
                signature=b"sig1",
                witness_type=WitnessType.KEEPER,
            ),
            CeremonyWitness(
                witness_id="KEEPER:bob",
                signature=b"sig2",
                witness_type=WitnessType.KEEPER,
            ),
        ]

        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:target",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            witnesses=witnesses,
        )

        assert ceremony.get_witness_ids() == ["KEEPER:alice", "KEEPER:bob"]

    def test_has_witness_true(self) -> None:
        """Check if witness has signed."""
        witnesses = [
            CeremonyWitness(
                witness_id="KEEPER:alice",
                signature=b"sig1",
                witness_type=WitnessType.KEEPER,
            ),
        ]

        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:target",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            witnesses=witnesses,
        )

        assert ceremony.has_witness("KEEPER:alice")

    def test_has_witness_false(self) -> None:
        """Check witness not signed."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:target",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        assert not ceremony.has_witness("KEEPER:alice")


class TestCeremonyTimeout:
    """Tests for ceremony timeout (VAL-2)."""

    def test_is_timed_out_fresh_ceremony(self) -> None:
        """VAL-2: Fresh ceremony is not timed out."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        assert not ceremony.is_timed_out()

    def test_is_timed_out_old_ceremony(self) -> None:
        """VAL-2: Old ceremony is timed out."""
        old_time = datetime.now(timezone.utc) - timedelta(
            seconds=CEREMONY_TIMEOUT_SECONDS + 1
        )

        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            created_at=old_time,
        )

        assert ceremony.is_timed_out()

    def test_is_timed_out_terminal_state_returns_false(self) -> None:
        """VAL-2: Terminal states cannot time out."""
        old_time = datetime.now(timezone.utc) - timedelta(
            seconds=CEREMONY_TIMEOUT_SECONDS + 1
        )

        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.COMPLETED,
            created_at=old_time,
        )

        # Even though it's old, completed ceremonies don't time out
        assert not ceremony.is_timed_out()


class TestCeremonyConstants:
    """Tests for ceremony constants."""

    def test_ceremony_timeout_is_one_hour(self) -> None:
        """VAL-2: Timeout is 1 hour (3600 seconds)."""
        assert CEREMONY_TIMEOUT_SECONDS == 3600

    def test_transition_period_is_30_days(self) -> None:
        """ADR-4: Transition period is 30 days."""
        assert TRANSITION_PERIOD_DAYS == 30

    def test_required_witnesses_is_three(self) -> None:
        """CT-12: Required witnesses is 3."""
        assert REQUIRED_WITNESSES == 3

    def test_valid_transitions_coverage(self) -> None:
        """FP-4: All states have defined transitions."""
        for state in CeremonyState:
            assert state in VALID_TRANSITIONS


class TestCeremonyWitnessModel:
    """Tests for CeremonyWitness value object."""

    def test_create_valid_witness(self) -> None:
        """Create valid witness."""
        witness = CeremonyWitness(
            witness_id="KEEPER:alice",
            signature=b"valid_signature",
            witness_type=WitnessType.KEEPER,
        )

        assert witness.witness_id == "KEEPER:alice"
        assert witness.signature == b"valid_signature"
        assert witness.witness_type == WitnessType.KEEPER

    def test_create_with_empty_witness_id_raises(self) -> None:
        """CT-12: Empty witness_id raises error."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            CeremonyWitness(
                witness_id="",
                signature=b"sig",
                witness_type=WitnessType.KEEPER,
            )

        assert "CT-12" in str(exc_info.value)

    def test_create_with_empty_signature_raises(self) -> None:
        """CT-12: Empty signature raises error."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            CeremonyWitness(
                witness_id="KEEPER:alice",
                signature=b"",
                witness_type=WitnessType.KEEPER,
            )

        assert "CT-12" in str(exc_info.value)

    def test_create_with_invalid_witness_type_raises(self) -> None:
        """CT-12: Invalid witness_type raises error."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            CeremonyWitness(
                witness_id="KEEPER:alice",
                signature=b"sig",
                witness_type="invalid",  # type: ignore
            )

        assert "CT-12" in str(exc_info.value)

    def test_witness_is_immutable(self) -> None:
        """Witness is frozen (immutable)."""
        witness = CeremonyWitness(
            witness_id="KEEPER:alice",
            signature=b"sig",
            witness_type=WitnessType.KEEPER,
        )

        with pytest.raises(AttributeError):
            witness.witness_id = "changed"  # type: ignore

    def test_witness_type_enum_values(self) -> None:
        """WitnessType enum has expected values."""
        assert WitnessType.KEEPER.value == "keeper"
        assert WitnessType.SYSTEM.value == "system"
        assert WitnessType.EXTERNAL.value == "external"
