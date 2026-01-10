"""Key generation ceremony domain model (FR69, ADR-4).

This module defines the KeyGenerationCeremony entity for tracking
witnessed key generation ceremonies for Keepers.

Constitutional Constraints:
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- FR76: Historical ceremony records must be preserved (no deletion)
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> Multiple witnesses required

ADR-4: Key Custody + Keeper Adversarial Defense:
1. Generate new key in HSM
2. Write key-transition event signed by old key referencing new public key
3. Activate new key for signing
4. Revoke old key after overlap period (30 days)

H2 Security Enhancement:
- Bootstrap mode can be disabled after initial setup
- WITNESS_BOOTSTRAP_ENABLED controls unverified witness acceptance
- Once disabled, all witnesses MUST have verified signatures

Note: DeletePreventionMixin ensures `.delete()` raises
ConstitutionalViolationError before any DB interaction.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.primitives import DeletePreventionMixin

if TYPE_CHECKING:
    from src.domain.models.ceremony_witness import CeremonyWitness

log = structlog.get_logger()

# VAL-2: Ceremony timeout enforcement - 1 hour max
CEREMONY_TIMEOUT_SECONDS: int = 3600

# ADR-4: 30-day transition period for key rotation
TRANSITION_PERIOD_DAYS: int = 30

# Minimum witnesses required for ceremony (CT-12)
REQUIRED_WITNESSES: int = 3

# H2 Security Fix: Bootstrap mode control for witness signature verification
# Set to "false" after initial system setup to require verified signatures
WITNESS_BOOTSTRAP_ENV_VAR: str = "WITNESS_BOOTSTRAP_ENABLED"


class BootstrapModeDisabledError(Exception):
    """Raised when bootstrap mode is disabled and unverified witness is attempted (H2 fix).

    After initial system setup, bootstrap mode should be disabled to require
    all witness signatures to be cryptographically verified.
    """

    pass


def is_witness_bootstrap_enabled() -> bool:
    """Check if witness bootstrap mode is enabled (H2 fix).

    Bootstrap mode allows witnesses without verified signatures during
    initial system setup. After setup, this should be disabled.

    Environment Variable:
        WITNESS_BOOTSTRAP_ENABLED: Set to "true" to allow unverified witnesses.
                                   Default is "true" for initial setup.
                                   Set to "false" after initial keeper setup.

    Returns:
        True if bootstrap mode is enabled, False otherwise.
    """
    return os.getenv(WITNESS_BOOTSTRAP_ENV_VAR, "true").lower() == "true"


def validate_bootstrap_mode_for_unverified_witness(witness_id: str) -> None:
    """Validate that bootstrap mode allows unverified witness (H2 fix).

    This function MUST be called before accepting an unverified witness
    signature. If bootstrap mode is disabled, it raises BootstrapModeDisabledError.

    H2 Security Finding:
    - During initial bootstrap, witnesses can sign without verification
    - This allows rogue witnesses to inject invalid attestations
    - This fix adds a configuration flag to disable bootstrap mode

    Args:
        witness_id: The ID of the witness without verified key.

    Raises:
        BootstrapModeDisabledError: If bootstrap mode is disabled.
    """
    if not is_witness_bootstrap_enabled():
        log.critical(
            "bootstrap_mode_disabled_unverified_witness_rejected",
            witness_id=witness_id,
            message="H2: Bootstrap mode disabled - unverified witness not allowed",
        )
        raise BootstrapModeDisabledError(
            f"H2 Security Violation: Bootstrap mode is disabled "
            f"(WITNESS_BOOTSTRAP_ENABLED=false). Witness '{witness_id}' "
            f"must have a registered key for signature verification. "
            f"Register the witness key first or enable bootstrap mode "
            f"for initial setup only."
        )


class CeremonyType(Enum):
    """Type of key generation ceremony.

    NEW_KEEPER_KEY: First key for a new Keeper
    KEY_ROTATION: Rotating existing key to new key with transition
    """

    NEW_KEEPER_KEY = "new_keeper_key"
    KEY_ROTATION = "key_rotation"


class CeremonyState(Enum):
    """State of the key generation ceremony (FP-4 state machine).

    State Transitions (VALID_TRANSITIONS):
    - PENDING -> APPROVED, EXPIRED, FAILED
    - APPROVED -> EXECUTING, EXPIRED
    - EXECUTING -> COMPLETED, FAILED
    - COMPLETED, FAILED, EXPIRED -> (terminal)
    """

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


# FP-4: Valid state transitions for ceremony state machine
VALID_TRANSITIONS: dict[CeremonyState, set[CeremonyState]] = {
    CeremonyState.PENDING: {
        CeremonyState.APPROVED,
        CeremonyState.EXPIRED,
        CeremonyState.FAILED,
    },
    CeremonyState.APPROVED: {
        CeremonyState.EXECUTING,
        CeremonyState.EXPIRED,
    },
    CeremonyState.EXECUTING: {
        CeremonyState.COMPLETED,
        CeremonyState.FAILED,
    },
    CeremonyState.COMPLETED: set(),  # Terminal
    CeremonyState.FAILED: set(),  # Terminal
    CeremonyState.EXPIRED: set(),  # Terminal
}


@dataclass(eq=True)
class KeyGenerationCeremony(DeletePreventionMixin):
    """Key generation ceremony entity - mutable state, deletion prohibited.

    Tracks the state of a witnessed key generation ceremony for a Keeper.
    Ceremonies transition through states per FP-4 state machine pattern.

    Constitutional Constraints:
    - FR69: Keeper keys require witnessed ceremony
    - FR76: Historical ceremonies must be preserved (no deletion)
    - CT-12: Multiple witnesses required for accountability

    Attributes:
        id: Unique identifier for this ceremony (UUID)
        keeper_id: ID of Keeper receiving the new key
        ceremony_type: NEW_KEEPER_KEY or KEY_ROTATION
        state: Current state in state machine
        witnesses: List of witnesses who have signed
        new_key_id: HSM key ID of new key (set after completion)
        old_key_id: HSM key ID of old key (for rotations)
        transition_end_at: When transition period ends (for rotations)
        created_at: When ceremony was initiated
        completed_at: When ceremony was completed (None if not completed)
        failure_reason: Reason for failure (None if not failed)

    Note:
        DeletePreventionMixin ensures `.delete()` raises
        ConstitutionalViolationError before any DB interaction.
    """

    # Primary identifier
    id: UUID

    # Keeper receiving the key (FR69)
    keeper_id: str

    # Type of ceremony
    ceremony_type: CeremonyType

    # Current state (FP-4 state machine)
    state: CeremonyState = field(default=CeremonyState.PENDING)

    # Witnesses who have signed (CT-12)
    witnesses: list[CeremonyWitness] = field(default_factory=list)

    # New key ID (set after generation)
    new_key_id: str | None = field(default=None)

    # Old key ID (for rotations)
    old_key_id: str | None = field(default=None)

    # Transition end date (ADR-4: 30 days for rotation)
    transition_end_at: datetime | None = field(default=None)

    # Audit timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = field(default=None)

    # Failure tracking
    failure_reason: str | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_id()
        self._validate_keeper_id()
        self._validate_ceremony_type()
        self._validate_state()

    def _validate_id(self) -> None:
        """Validate id is UUID."""
        if not isinstance(self.id, UUID):
            raise ConstitutionalViolationError(
                f"FR69: Ceremony validation failed - id must be UUID, got {type(self.id).__name__}"
            )

    def _validate_keeper_id(self) -> None:
        """Validate keeper_id is non-empty string."""
        if not isinstance(self.keeper_id, str) or not self.keeper_id.strip():
            raise ConstitutionalViolationError(
                "FR69: Ceremony validation failed - keeper_id must be non-empty string"
            )

    def _validate_ceremony_type(self) -> None:
        """Validate ceremony_type is CeremonyType enum."""
        if not isinstance(self.ceremony_type, CeremonyType):
            raise ConstitutionalViolationError(
                f"FR69: Ceremony validation failed - ceremony_type must be CeremonyType, got {type(self.ceremony_type).__name__}"
            )

    def _validate_state(self) -> None:
        """Validate state is CeremonyState enum."""
        if not isinstance(self.state, CeremonyState):
            raise ConstitutionalViolationError(
                f"FR69: Ceremony validation failed - state must be CeremonyState, got {type(self.state).__name__}"
            )

    def __hash__(self) -> int:
        """Hash based on id (unique identifier)."""
        return hash(self.id)

    def can_transition_to(self, new_state: CeremonyState) -> bool:
        """Check if transition to new_state is valid (FP-4).

        Args:
            new_state: The target state.

        Returns:
            True if transition is valid, False otherwise.
        """
        return new_state in VALID_TRANSITIONS.get(self.state, set())

    def transition_to(self, new_state: CeremonyState) -> None:
        """Transition to new state if valid (FP-4 state machine).

        Args:
            new_state: The target state.

        Raises:
            ConstitutionalViolationError: If transition is invalid.
        """
        if not self.can_transition_to(new_state):
            raise ConstitutionalViolationError(
                f"FP-4: Invalid state transition {self.state.value} -> {new_state.value}"
            )
        self.state = new_state

    def is_terminal(self) -> bool:
        """Check if ceremony is in terminal state.

        Returns:
            True if COMPLETED, FAILED, or EXPIRED.
        """
        return self.state in {
            CeremonyState.COMPLETED,
            CeremonyState.FAILED,
            CeremonyState.EXPIRED,
        }

    def is_active(self) -> bool:
        """Check if ceremony is active (not terminal).

        Returns:
            True if PENDING, APPROVED, or EXECUTING.
        """
        return not self.is_terminal()

    def has_sufficient_witnesses(self) -> bool:
        """Check if ceremony has required number of witnesses (CT-12).

        Returns:
            True if witnesses >= REQUIRED_WITNESSES.
        """
        return len(self.witnesses) >= REQUIRED_WITNESSES

    def is_timed_out(self) -> bool:
        """Check if ceremony has exceeded timeout (VAL-2).

        Returns:
            True if elapsed time > CEREMONY_TIMEOUT_SECONDS.
        """
        if self.is_terminal():
            return False
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > CEREMONY_TIMEOUT_SECONDS

    def get_witness_ids(self) -> list[str]:
        """Get list of witness IDs who have signed.

        Returns:
            List of witness_id strings.
        """
        return [w.witness_id for w in self.witnesses]

    def has_witness(self, witness_id: str) -> bool:
        """Check if witness has already signed.

        Args:
            witness_id: ID of the witness to check.

        Returns:
            True if witness has already signed this ceremony.
        """
        return witness_id in self.get_witness_ids()
