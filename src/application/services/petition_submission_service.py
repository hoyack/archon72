"""Petition Submission Service (Story 1.1/1.2, FR-1.1/FR-1.7).

This service orchestrates the petition submission workflow for the
Three Fates deliberation system.

Constitutional Constraints:
- FR-1.1: Accept petition submissions via REST API
- FR-1.2: Generate UUID petition_id on submission
- FR-1.3: Validate petition schema (type, text)
- FR-1.6: Set initial state to RECEIVED
- FR-1.7: Emit PetitionReceived event on successful intake
- CT-11: Silent failure destroys legitimacy - fail loud on errors
- CT-12: Witnessing creates accountability - all actions logged
- CT-13: No writes during halt - event emission also blocked
- HP-2: Content hashing for duplicate detection

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before any write
2. FAIL LOUD - Raise exceptions on errors
3. LOG EVERYTHING - All operations have structured logging
4. EVENT AFTER SAVE - Emit event only after successful persistence
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.application.ports.content_hash_service import ContentHashServiceProtocol
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.petition_event_emitter import PetitionEventEmitterPort
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.application.ports.realm_registry import RealmRegistryProtocol
from src.application.services.base import LoggingMixin
from src.domain.errors import FateEventEmissionError, SystemHaltedError
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)


class InvalidRealmError(Exception):
    """Raised when a petition specifies an invalid realm."""

    pass


class PetitionSubmissionResult:
    """Result of a petition submission operation.

    Attributes:
        petition_id: The generated petition identifier.
        state: The initial state (RECEIVED).
        petition_type: The type of petition.
        content_hash: Base64-encoded Blake3 hash.
        realm: The assigned realm.
        created_at: When the petition was created.
    """

    def __init__(
        self,
        petition_id: UUID,
        state: PetitionState,
        petition_type: PetitionType,
        content_hash: str,
        realm: str,
        created_at: datetime,
    ) -> None:
        self.petition_id = petition_id
        self.state = state
        self.petition_type = petition_type
        self.content_hash = content_hash
        self.realm = realm
        self.created_at = created_at


class PetitionSubmissionService(LoggingMixin):
    """Service for handling petition submissions (Story 1.1/1.2, FR-1.1/FR-1.7).

    Orchestrates the petition submission workflow:
    1. Check halt state (HALT FIRST rule)
    2. Validate realm (if specified)
    3. Compute content hash (HP-2)
    4. Generate petition ID
    5. Save petition with RECEIVED state
    6. Emit petition.received event (FR-1.7)
    7. Return submission result

    Constitutional Constraints:
    - FR-1.1: Accept submissions via service layer
    - FR-1.2: Generate UUID petition_id
    - FR-1.3: Validate schema
    - FR-1.6: Set initial state to RECEIVED
    - FR-1.7: Emit PetitionReceived event on successful intake
    - HP-2: Content hashing for duplicate detection
    - CT-11: Fail loud on errors
    - CT-12: All operations logged

    Attributes:
        _repository: Petition submission repository.
        _hash_service: Content hash service.
        _realm_registry: Realm registry for routing.
        _halt_checker: Halt state checker.
        _event_emitter: Event emitter for petition lifecycle events.
    """

    def __init__(
        self,
        repository: PetitionSubmissionRepositoryProtocol,
        hash_service: ContentHashServiceProtocol,
        realm_registry: RealmRegistryProtocol,
        halt_checker: HaltChecker,
        event_emitter: PetitionEventEmitterPort | None = None,
    ) -> None:
        """Initialize the petition submission service.

        Args:
            repository: Repository for petition persistence.
            hash_service: Service for content hashing.
            realm_registry: Registry for realm validation and routing.
            halt_checker: Service to check system halt state.
            event_emitter: Optional event emitter for lifecycle events (FR-1.7).
                           If None, event emission is skipped.
        """
        self._repository = repository
        self._hash_service = hash_service
        self._realm_registry = realm_registry
        self._halt_checker = halt_checker
        self._event_emitter = event_emitter
        self._init_logger(component="petition")

    async def submit_petition(
        self,
        petition_type: PetitionType,
        text: str,
        realm: str | None = None,
        submitter_id: UUID | None = None,
    ) -> PetitionSubmissionResult:
        """Submit a new petition to the Three Fates system.

        Constitutional Constraints:
        - FR-1.1: Accept submission
        - FR-1.2: Generate UUID petition_id
        - FR-1.6: Set state to RECEIVED
        - FR-1.7: Emit petition.received event
        - HP-2: Compute content hash
        - CT-11: Fail loud on errors

        Args:
            petition_type: Type of petition (GENERAL, CESSATION, etc.)
            text: Petition content (1-10,000 chars)
            realm: Optional realm identifier for routing
            submitter_id: Optional submitter identity

        Returns:
            PetitionSubmissionResult with petition details

        Raises:
            SystemHaltedError: If system is halted (CT-13)
            InvalidRealmError: If specified realm is invalid
            ValueError: If petition text is invalid
        """
        log = self._log_operation(
            "submit_petition",
            petition_type=petition_type.value,
            text_length=len(text),
            realm=realm,
        )

        # HALT CHECK FIRST (CT-13)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.warning("submission_rejected_halt", halt_reason=reason)
            raise SystemHaltedError(reason or "System is halted")

        log.info("submission_started")

        # Validate realm (HP-3)
        resolved_realm = await self._resolve_realm(realm)
        log.debug("realm_resolved", resolved_realm=resolved_realm)

        # Compute content hash (HP-2)
        content_hash_bytes = self._hash_service.hash_text(text)
        content_hash_b64 = base64.b64encode(content_hash_bytes).decode("ascii")
        log.debug("content_hash_computed", hash_prefix=content_hash_b64[:8])

        # Generate petition ID (FR-1.2)
        petition_id = uuid4()
        created_at = datetime.now(timezone.utc)

        # Create petition submission (FR-1.6)
        submission = PetitionSubmission(
            id=petition_id,
            type=petition_type,
            text=text,
            state=PetitionState.RECEIVED,
            submitter_id=submitter_id,
            content_hash=content_hash_bytes,
            realm=resolved_realm,
            created_at=created_at,
            updated_at=created_at,
        )

        # Save to repository
        await self._repository.save(submission)
        log.info(
            "submission_completed",
            petition_id=str(petition_id),
            state=PetitionState.RECEIVED.value,
        )

        # Emit petition.received event (FR-1.7)
        # Event emission errors are logged but don't fail the submission
        # The petition is already persisted - event is for observability
        if self._event_emitter is not None:
            event_emitted = await self._event_emitter.emit_petition_received(
                petition_id=petition_id,
                petition_type=petition_type.value,
                realm=resolved_realm,
                content_hash=content_hash_b64,
                submitter_id=submitter_id,
            )
            if event_emitted:
                log.debug("event_emitted", event_type="petition.received")
            else:
                log.warning("event_emission_failed", event_type="petition.received")

        return PetitionSubmissionResult(
            petition_id=petition_id,
            state=PetitionState.RECEIVED,
            petition_type=petition_type,
            content_hash=content_hash_b64,
            realm=resolved_realm,
            created_at=created_at,
        )

    async def _resolve_realm(self, realm: str | None) -> str:
        """Resolve and validate the realm for petition routing.

        If realm is specified, validates it exists.
        If not specified, uses the default realm.

        Args:
            realm: Optional realm identifier

        Returns:
            Resolved realm name

        Raises:
            InvalidRealmError: If specified realm doesn't exist
        """
        if realm is None:
            # Use default realm
            default_realm = self._realm_registry.get_default_realm()
            if default_realm is None:
                return "default"
            return default_realm.name

        # Validate specified realm exists
        found_realm = self._realm_registry.get_realm_by_name(realm)
        if found_realm is None:
            raise InvalidRealmError(f"Unknown realm: {realm}")

        return found_realm.name

    async def get_petition(self, petition_id: UUID) -> PetitionSubmission | None:
        """Retrieve a petition submission by ID.

        Args:
            petition_id: The petition identifier

        Returns:
            PetitionSubmission if found, None otherwise
        """
        log = self._log_operation("get_petition", petition_id=str(petition_id))
        submission = await self._repository.get(petition_id)

        if submission is None:
            log.debug("petition_not_found")
        else:
            log.debug("petition_found", state=submission.state.value)

        return submission

    async def assign_fate_transactional(
        self,
        petition_id: UUID,
        expected_state: PetitionState,
        new_state: PetitionState,
        actor_id: str,
        reason: str | None = None,
    ) -> PetitionSubmission:
        """Assign fate to petition with transactional event emission (Story 1.7, FR-2.5).

        This method combines CAS state update with fate event emission in a
        transactional pattern. If event emission fails, the state change is
        rolled back to maintain constitutional invariant HC-1.

        Pattern: CAS state update → emit event → commit OR rollback

        Constitutional Constraints:
        - FR-2.4: System SHALL use atomic CAS for fate assignment
        - FR-2.5: System SHALL emit fate event in same transaction as state update
        - HC-1: Fate transition requires witness event - NO silent fate assignment
        - NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
        - NFR-3.3: Event witnessing: 100% fate events persisted [CRITICAL]
        - CT-13: No writes during halt

        Args:
            petition_id: The petition to assign fate to.
            expected_state: The state petition must be in for CAS to succeed.
            new_state: Terminal fate state (ACKNOWLEDGED, REFERRED, ESCALATED).
            actor_id: Agent or system identifier assigning the fate.
            reason: Optional rationale for the fate decision.

        Returns:
            Updated PetitionSubmission with new fate state.

        Raises:
            SystemHaltedError: If system is halted (CT-13).
            ConcurrentModificationError: If expected_state doesn't match (FR-2.4).
            PetitionAlreadyFatedError: If petition already has terminal fate.
            FateEventEmissionError: If event emission fails (state rolled back).
        """
        log = self._log_operation(
            "assign_fate_transactional",
            petition_id=str(petition_id),
            expected_state=expected_state.value,
            new_state=new_state.value,
            actor_id=actor_id,
        )

        # HALT CHECK FIRST (CT-13)
        if await self._halt_checker.is_halted():
            halt_reason = await self._halt_checker.get_halt_reason()
            log.warning("fate_assignment_rejected_halt", halt_reason=halt_reason)
            raise SystemHaltedError(halt_reason or "System is halted")

        log.info("fate_assignment_started")

        # Step 1: Perform CAS state update (Story 1.6, FR-2.4)
        # This raises ConcurrentModificationError if expected_state doesn't match
        updated_petition = await self._repository.assign_fate_cas(
            petition_id, expected_state, new_state
        )
        log.debug(
            "cas_state_updated",
            previous_state=expected_state.value,
            new_state=new_state.value,
        )

        # Step 2: Emit fate event (MUST succeed or rollback) (FR-2.5, HC-1)
        if self._event_emitter is None:
            # No event emitter configured - this violates HC-1
            # Rollback and raise error
            log.error("no_event_emitter_configured")
            await self._repository.update_state(petition_id, expected_state)
            raise FateEventEmissionError(
                petition_id=petition_id,
                new_state=new_state.value,
                cause=RuntimeError("Event emitter not configured"),
            )

        try:
            await self._event_emitter.emit_fate_event(
                petition_id=petition_id,
                previous_state=expected_state.value,
                new_state=new_state.value,
                actor_id=actor_id,
                reason=reason,
            )
            log.info(
                "fate_assignment_completed",
                petition_id=str(petition_id),
                new_state=new_state.value,
                actor_id=actor_id,
            )
        except Exception as e:
            # CRITICAL: Rollback state change (HC-1)
            log.error(
                "fate_event_emission_failed_rolling_back",
                petition_id=str(petition_id),
                error=str(e),
                error_type=type(e).__name__,
            )
            await self._repository.update_state(petition_id, expected_state)
            log.warning(
                "fate_state_rolled_back",
                petition_id=str(petition_id),
                rolled_back_to=expected_state.value,
            )
            raise FateEventEmissionError(
                petition_id=petition_id,
                new_state=new_state.value,
                cause=e,
            ) from e

        return updated_petition
