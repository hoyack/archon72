"""Acknowledgment execution stub for testing (Story 3.2, 3.5).

This module provides stub implementations of the acknowledgment protocols
for use in unit tests and integration tests.

Constitutional Context:
- FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
- FR-3.5: System SHALL enforce minimum dwell time before ACKNOWLEDGE
- CT-12: Every action that affects an Archon must be witnessed
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.errors.acknowledgment import (
    AcknowledgmentAlreadyExistsError,
    DeliberationSessionNotFoundError,
    DwellTimeNotElapsedError,
    InvalidArchonCountError,
    InvalidReferencePetitionError,
    PetitionNotFoundError,
    PetitionNotInDeliberatingStateError,
)
from src.domain.events.acknowledgment import PetitionAcknowledgedEvent
from src.domain.models.acknowledgment import (
    MIN_ACKNOWLEDGING_ARCHONS,
    Acknowledgment,
)
from src.domain.models.acknowledgment_reason import (
    AcknowledgmentReasonCode,
    validate_acknowledgment_requirements,
)

if TYPE_CHECKING:
    from src.domain.models.deliberation_session import DeliberationSession
    from src.domain.models.petition_submission import PetitionSubmission


class AcknowledgmentExecutionStub:
    """Stub implementation for acknowledgment execution testing.

    Provides in-memory storage and configurable behavior for testing
    the acknowledgment execution flow without database dependencies.

    Example:
        >>> stub = AcknowledgmentExecutionStub()
        >>> stub.add_petition(petition)  # Add test petition
        >>> ack = await stub.execute(
        ...     petition_id=petition.id,
        ...     reason_code=AcknowledgmentReasonCode.NOTED,
        ...     acknowledging_archon_ids=(15, 42),
        ... )
        >>> assert stub.was_executed(petition.id)
    """

    def __init__(
        self,
        config: DeliberationConfig | None = None,
        enforce_dwell_time: bool = False,
    ) -> None:
        """Initialize the stub with empty storage.

        Args:
            config: Deliberation configuration including dwell time settings
            enforce_dwell_time: If True, enforce dwell time validation (FR-3.5)
        """
        self._acknowledgments: dict[UUID, Acknowledgment] = {}
        self._acknowledgments_by_petition: dict[UUID, Acknowledgment] = {}
        self._petitions: dict[UUID, PetitionSubmission] = {}
        self._sessions: dict[UUID, DeliberationSession] = {}  # petition_id -> session
        self._emitted_events: list[dict] = []
        self._execution_count: int = 0
        self._config = config or DEFAULT_DELIBERATION_CONFIG
        self._enforce_dwell_time = enforce_dwell_time

        # Test control flags
        self._fail_hash_generation: bool = False
        self._hash_generation_error_message: str = "Hash generation failed"

    def add_petition(
        self,
        petition: PetitionSubmission,
        session: DeliberationSession | None = None,
    ) -> None:
        """Add a petition to the stub's storage.

        Args:
            petition: The petition to add for testing
            session: Optional deliberation session for dwell time testing
        """
        self._petitions[petition.id] = petition
        if session is not None:
            self._sessions[petition.id] = session

    def add_session(self, petition_id: UUID, session: DeliberationSession) -> None:
        """Add a deliberation session for dwell time testing.

        Args:
            petition_id: The petition UUID
            session: The deliberation session
        """
        self._sessions[petition_id] = session

    def set_fail_hash_generation(
        self, fail: bool, message: str = "Hash generation failed"
    ) -> None:
        """Configure hash generation to fail for testing error paths.

        Args:
            fail: If True, hash generation will fail
            message: Error message to use
        """
        self._fail_hash_generation = fail
        self._hash_generation_error_message = message

    async def execute(
        self,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        acknowledging_archon_ids: Sequence[int],
        rationale: str | None = None,
        reference_petition_id: UUID | None = None,
    ) -> Acknowledgment:
        """Execute acknowledgment (stub implementation).

        Mirrors the real service's validation and behavior.

        Args:
            petition_id: The petition to acknowledge
            reason_code: Reason for acknowledgment
            acknowledging_archon_ids: IDs of archons who voted ACKNOWLEDGE
            rationale: Required for REFUSED/NO_ACTION_WARRANTED
            reference_petition_id: Required for DUPLICATE

        Returns:
            The created Acknowledgment record

        Raises:
            Various validation errors matching the real service
        """
        self._execution_count += 1

        # Validate archon count
        if len(acknowledging_archon_ids) < MIN_ACKNOWLEDGING_ARCHONS:
            raise InvalidArchonCountError(
                actual_count=len(acknowledging_archon_ids),
                required_count=MIN_ACKNOWLEDGING_ARCHONS,
            )

        # Validate reason code requirements
        validate_acknowledgment_requirements(
            reason_code=reason_code,
            rationale=rationale,
            reference_petition_id=reference_petition_id,
        )

        # Check petition exists
        petition = self._petitions.get(petition_id)
        if petition is None:
            raise PetitionNotFoundError(petition_id)

        # Check petition state
        from src.domain.models.petition_submission import PetitionState

        if petition.state != PetitionState.DELIBERATING:
            raise PetitionNotInDeliberatingStateError(
                petition_id=petition_id,
                current_state=petition.state.value,
            )

        # Check dwell time (FR-3.5) if enforcement is enabled
        if self._enforce_dwell_time and self._config.min_dwell_seconds > 0:
            session = self._sessions.get(petition_id)
            if session is None:
                raise DeliberationSessionNotFoundError(petition_id)

            now = datetime.now(timezone.utc)
            elapsed = (now - session.created_at).total_seconds()
            if elapsed < self._config.min_dwell_seconds:
                raise DwellTimeNotElapsedError(
                    petition_id=petition_id,
                    deliberation_started_at=session.created_at,
                    min_dwell_seconds=self._config.min_dwell_seconds,
                    elapsed_seconds=elapsed,
                )

        # Check for existing acknowledgment
        if petition_id in self._acknowledgments_by_petition:
            return self._acknowledgments_by_petition[petition_id]

        # Validate reference petition
        if reference_petition_id is not None:
            if reference_petition_id not in self._petitions:
                raise InvalidReferencePetitionError(
                    petition_id=petition_id,
                    reference_petition_id=reference_petition_id,
                )

        # Generate hash (may fail for testing)
        if self._fail_hash_generation:
            from src.domain.errors.acknowledgment import WitnessHashGenerationError

            raise WitnessHashGenerationError(
                petition_id=petition_id,
                reason=self._hash_generation_error_message,
            )

        acknowledgment_id = uuid4()
        acknowledged_at = datetime.now(timezone.utc)
        witness_hash = f"blake3:stub_{acknowledgment_id.hex[:16]}"

        # Create acknowledgment
        acknowledgment = Acknowledgment.create(
            id=acknowledgment_id,
            petition_id=petition_id,
            reason_code=reason_code,
            acknowledging_archon_ids=acknowledging_archon_ids,
            acknowledged_at=acknowledged_at,
            witness_hash=witness_hash,
            rationale=rationale,
            reference_petition_id=reference_petition_id,
        )

        # Store
        self._acknowledgments[acknowledgment.id] = acknowledgment
        self._acknowledgments_by_petition[petition_id] = acknowledgment

        # Emit event
        event = PetitionAcknowledgedEvent.from_acknowledgment(
            event_id=uuid4(),
            acknowledgment_id=acknowledgment.id,
            petition_id=petition_id,
            reason_code=reason_code,
            acknowledging_archon_ids=acknowledgment.acknowledging_archon_ids,
            acknowledged_at=acknowledged_at,
            witness_hash=witness_hash,
            rationale=rationale,
            reference_petition_id=reference_petition_id,
        )
        self._emitted_events.append(event.to_dict())

        return acknowledgment

    async def execute_king_acknowledge(
        self,
        petition_id: UUID,
        king_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        rationale: str,
        realm_id: str,
    ) -> Acknowledgment:
        """Execute King acknowledgment of escalated petition (Story 6.5, FR-5.8).

        Args:
            petition_id: The escalated petition to acknowledge.
            king_id: UUID of the King acknowledging.
            reason_code: Reason from AcknowledgmentReasonCode enum.
            rationale: King's explanation (min 100 chars).
            realm_id: Realm ID for authorization.

        Returns:
            The created Acknowledgment record.

        Raises:
            PetitionNotFoundError: Petition doesn't exist.
            PetitionNotEscalatedError: Petition not in ESCALATED state.
            ValueError: Rationale too short (< 100 chars).
            RealmMismatchError: King's realm doesn't match petition's realm.
        """
        from src.domain.errors.petition import (
            PetitionNotEscalatedError,
            RealmMismatchError,
        )
        from src.domain.models.petition_submission import PetitionState

        self._execution_count += 1

        # Validate rationale length (Story 6.5 AC2: min 100 chars)
        MIN_KING_RATIONALE_LENGTH = 100
        if not rationale or len(rationale.strip()) < MIN_KING_RATIONALE_LENGTH:
            raise ValueError(
                f"King acknowledgment requires rationale >= {MIN_KING_RATIONALE_LENGTH} chars, "
                f"got {len(rationale.strip()) if rationale else 0} chars. "
                f"Kings have a higher bar for explaining decisions to petitioners (FR-5.8)."
            )

        # Get petition and validate existence
        petition = self._petitions.get(petition_id)
        if petition is None:
            raise PetitionNotFoundError(petition_id)

        # Validate petition is in ESCALATED state (Story 6.5 AC3)
        if petition.state != PetitionState.ESCALATED:
            raise PetitionNotEscalatedError(
                petition_id=petition_id,
                current_state=petition.state.value,
                message=f"King can only acknowledge ESCALATED petitions, "
                        f"but petition {petition_id} is in {petition.state.value} state."
            )

        # Validate realm authorization (Story 6.5 AC4, RULING-3)
        if petition.escalated_to_realm != realm_id:
            raise RealmMismatchError(
                expected_realm=petition.escalated_to_realm or "unknown",
                actual_realm=realm_id,
                message=f"King from realm '{realm_id}' cannot acknowledge petition "
                        f"escalated to realm '{petition.escalated_to_realm}' (RULING-3)."
            )

        # Validate acknowledgment requirements (FR-3.3, FR-3.4)
        validate_acknowledgment_requirements(
            reason_code,
            rationale,
            None,  # reference_petition_id not used for King acknowledgments
        )

        # Check for existing acknowledgment (idempotency)
        existing = self._acknowledgments_by_petition.get(petition_id)
        if existing is not None:
            raise AcknowledgmentAlreadyExistsError(
                petition_id=petition_id,
                existing_acknowledgment_id=existing.id,
            )

        # Generate hash
        if self._fail_hash_generation:
            from src.domain.errors.acknowledgment import WitnessHashGenerationError

            raise WitnessHashGenerationError(
                petition_id=petition_id,
                reason=self._hash_generation_error_message,
            )

        acknowledgment_id = uuid4()
        acknowledged_at = datetime.now(timezone.utc)
        witness_hash = f"blake3:stub_king_{acknowledgment_id.hex[:16]}"

        # Create acknowledgment (with King ID)
        acknowledgment = Acknowledgment.create(
            id=acknowledgment_id,
            petition_id=petition_id,
            reason_code=reason_code,
            acknowledging_archon_ids=[],  # Empty for King acknowledgments
            acknowledged_by_king_id=king_id,  # King ID recorded here
            acknowledged_at=acknowledged_at,
            witness_hash=witness_hash,
            rationale=rationale,
            reference_petition_id=None,
        )

        # Store
        self._acknowledgments[acknowledgment.id] = acknowledgment
        self._acknowledgments_by_petition[petition_id] = acknowledgment

        # Emit KingAcknowledgedEscalation event (Story 6.5 AC7)
        event = {
            "event_type": "petition.escalation.acknowledged_by_king",
            "petition_id": petition_id,
            "king_id": king_id,
            "reason_code": reason_code.value,
            "rationale": rationale,
            "acknowledged_at": acknowledged_at.isoformat(),
            "realm_id": realm_id,
            "witness_hash": witness_hash,
        }
        self._emitted_events.append(event)

        return acknowledgment

    async def get_acknowledgment(
        self,
        acknowledgment_id: UUID,
    ) -> Acknowledgment | None:
        """Retrieve an acknowledgment by ID."""
        return self._acknowledgments.get(acknowledgment_id)

    async def get_acknowledgment_by_petition(
        self,
        petition_id: UUID,
    ) -> Acknowledgment | None:
        """Retrieve an acknowledgment by petition ID."""
        return self._acknowledgments_by_petition.get(petition_id)

    # Test helper methods

    def was_executed(self, petition_id: UUID) -> bool:
        """Check if a petition was acknowledged.

        Args:
            petition_id: The petition to check

        Returns:
            True if the petition was acknowledged
        """
        return petition_id in self._acknowledgments_by_petition

    def get_execution_count(self) -> int:
        """Get the number of times execute was called.

        Returns:
            Total execution attempts (including failures)
        """
        return self._execution_count

    def get_emitted_events(self) -> list[dict]:
        """Get all emitted events.

        Returns:
            List of event dictionaries
        """
        return list(self._emitted_events)

    def get_last_emitted_event(self) -> dict | None:
        """Get the most recently emitted event.

        Returns:
            The last event dictionary, or None if no events
        """
        return self._emitted_events[-1] if self._emitted_events else None

    def clear(self) -> None:
        """Clear all stored state."""
        self._acknowledgments.clear()
        self._acknowledgments_by_petition.clear()
        self._petitions.clear()
        self._emitted_events.clear()
        self._execution_count = 0
        self._fail_hash_generation = False


class AcknowledgmentRepositoryStub:
    """Stub repository for acknowledgment persistence testing.

    Provides in-memory storage matching the AcknowledgmentRepositoryProtocol.
    """

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._acknowledgments: dict[UUID, Acknowledgment] = {}
        self._by_petition: dict[UUID, Acknowledgment] = {}

    async def save(self, acknowledgment: Acknowledgment) -> None:
        """Persist an acknowledgment."""
        if acknowledgment.petition_id in self._by_petition:
            existing = self._by_petition[acknowledgment.petition_id]
            raise AcknowledgmentAlreadyExistsError(
                petition_id=acknowledgment.petition_id,
                existing_acknowledgment_id=existing.id,
            )
        self._acknowledgments[acknowledgment.id] = acknowledgment
        self._by_petition[acknowledgment.petition_id] = acknowledgment

    async def get_by_id(self, acknowledgment_id: UUID) -> Acknowledgment | None:
        """Retrieve by ID."""
        return self._acknowledgments.get(acknowledgment_id)

    async def get_by_petition_id(self, petition_id: UUID) -> Acknowledgment | None:
        """Retrieve by petition ID."""
        return self._by_petition.get(petition_id)

    async def exists_for_petition(self, petition_id: UUID) -> bool:
        """Check if acknowledgment exists."""
        return petition_id in self._by_petition

    def clear(self) -> None:
        """Clear all stored acknowledgments."""
        self._acknowledgments.clear()
        self._by_petition.clear()
