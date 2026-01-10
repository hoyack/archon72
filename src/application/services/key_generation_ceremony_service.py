"""Key Generation Ceremony Service (FR69, ADR-4).

This service orchestrates witnessed key generation ceremonies for Keepers.
All Keeper key generation MUST go through this service to ensure:
1. Multiple witnesses attest to the ceremony (CT-12)
2. Ceremonies are properly recorded as constitutional events
3. Key transitions follow ADR-4 requirements (30-day overlap)

Constitutional Constraints:
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- FR70: Every override SHALL record full authorization chain
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> Multiple witnesses required
- VAL-2: Ceremony timeout enforcement (1 hour max)
- CM-5: Single ceremony at a time per Keeper

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All state changes are witnessed events
3. FAIL LOUD - Invalid operations raise immediately with FR reference
4. NO SHORTCUTS - All transitions go through state machine
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from structlog import get_logger

from src.application.ports.hsm import HSMProtocol
from src.application.ports.keeper_key_registry import KeeperKeyRegistryProtocol
from src.application.ports.key_generation_ceremony import KeyGenerationCeremonyProtocol
from src.domain.errors.key_generation_ceremony import (
    CeremonyConflictError,
    CeremonyNotFoundError,
    DuplicateWitnessError,
    InsufficientWitnessesError,
    InvalidCeremonyStateError,
    InvalidWitnessSignatureError,
)
from src.domain.events.key_generation_ceremony import (
    KEY_GENERATION_CEREMONY_COMPLETED_EVENT_TYPE,
    KEY_GENERATION_CEREMONY_FAILED_EVENT_TYPE,
    KEY_GENERATION_CEREMONY_STARTED_EVENT_TYPE,
    KEY_GENERATION_CEREMONY_WITNESSED_EVENT_TYPE,
    KeyGenerationCeremonyCompletedPayload,
    KeyGenerationCeremonyFailedPayload,
    KeyGenerationCeremonyStartedPayload,
    KeyGenerationCeremonyWitnessedPayload,
)
from src.domain.models.ceremony_witness import CeremonyWitness, WitnessType
from src.domain.models.keeper_key import KeeperKey
from src.domain.models.key_generation_ceremony import (
    CEREMONY_TIMEOUT_SECONDS,
    REQUIRED_WITNESSES,
    TRANSITION_PERIOD_DAYS,
    BootstrapModeDisabledError,
    CeremonyState,
    CeremonyType,
    KeyGenerationCeremony,
    is_witness_bootstrap_enabled,
    validate_bootstrap_mode_for_unverified_witness,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService
    from src.application.services.halt_guard import HaltGuard

logger = get_logger()


class KeyGenerationCeremonyService:
    """Service for orchestrating Keeper key generation ceremonies (FR69).

    This service provides:
    1. start_ceremony(): Initiate a new key generation ceremony
    2. add_witness(): Add witness attestation to a ceremony
    3. execute_ceremony(): Complete ceremony and register new key
    4. check_ceremony_timeout(): Background task for timeout enforcement

    All Keeper key generation MUST use this service.

    Constitutional Constraints:
    - FR69: Keeper keys require witnessed ceremony
    - CT-11: HALT CHECK FIRST at every operation
    - CT-12: Multiple witnesses required (REQUIRED_WITNESSES = 3)
    - VAL-2: Ceremony timeout (CEREMONY_TIMEOUT_SECONDS = 3600)
    - CM-5: Single active ceremony per Keeper

    Attributes:
        _hsm: HSM protocol for key generation.
        _key_registry: Keeper key registry for key management.
        _ceremony_repo: Ceremony repository for ceremony tracking.
        _event_writer: Event writer for constitutional events.
        _halt_guard: Halt guard for halt state checking.
    """

    def __init__(
        self,
        hsm: HSMProtocol,
        key_registry: KeeperKeyRegistryProtocol,
        ceremony_repo: KeyGenerationCeremonyProtocol,
        event_writer: EventWriterService | None = None,
        halt_guard: HaltGuard | None = None,
    ) -> None:
        """Initialize the Key Generation Ceremony Service.

        Args:
            hsm: HSM protocol for key generation.
            key_registry: Keeper key registry for key management.
            ceremony_repo: Ceremony repository for tracking.
            event_writer: Optional event writer for constitutional events.
            halt_guard: Optional halt guard for halt state checking.
        """
        self._hsm = hsm
        self._key_registry = key_registry
        self._ceremony_repo = ceremony_repo
        self._event_writer = event_writer
        self._halt_guard = halt_guard

    async def start_ceremony(
        self,
        keeper_id: str,
        ceremony_type: CeremonyType,
        initiator_id: str,
        old_key_id: str | None = None,
    ) -> KeyGenerationCeremony:
        """Start a new key generation ceremony (FR69).

        Creates a ceremony in PENDING state, ready for witnesses.
        HALT CHECK is performed first per CT-11.

        Args:
            keeper_id: ID of Keeper receiving the new key.
            ceremony_type: NEW_KEEPER_KEY or KEY_ROTATION.
            initiator_id: Who started the ceremony (e.g., "KEEPER:admin").
            old_key_id: HSM key ID being rotated (for rotations).

        Returns:
            The newly created KeyGenerationCeremony.

        Raises:
            WriteBlockedDuringHaltError: If system is halted.
            CeremonyConflictError: If active ceremony exists for Keeper (CM-5).
        """
        log = logger.bind(
            operation="start_ceremony",
            keeper_id=keeper_id,
            ceremony_type=ceremony_type.value,
            initiator_id=initiator_id,
        )

        # CT-11: HALT CHECK FIRST
        if self._halt_guard:
            await self._halt_guard.check_write_allowed()

        # CM-5: Check for conflicting active ceremony
        existing = await self._ceremony_repo.get_active_ceremony_for_keeper(keeper_id)
        if existing:
            log.warning(
                "ceremony_conflict",
                existing_id=str(existing.id),
                message="CM-5: Active ceremony already exists",
            )
            raise CeremonyConflictError(
                f"CM-5: Conflicting ceremony already active for {keeper_id}: {existing.id}"
            )

        # Create ceremony
        ceremony = await self._ceremony_repo.create_ceremony(
            keeper_id=keeper_id,
            ceremony_type=ceremony_type,
            old_key_id=old_key_id,
        )

        log.info(
            "ceremony_started",
            ceremony_id=str(ceremony.id),
            message="Key generation ceremony started",
        )

        # Write started event
        if self._event_writer:
            payload = KeyGenerationCeremonyStartedPayload(
                ceremony_id=ceremony.id,
                keeper_id=keeper_id,
                ceremony_type=ceremony_type.value,
                initiator_id=initiator_id,
                old_key_id=old_key_id,
            )
            await self._event_writer.write_event(
                event_type=KEY_GENERATION_CEREMONY_STARTED_EVENT_TYPE,
                payload=payload.to_dict(),
                agent_id="SYSTEM:ceremony_service",
            )

        return ceremony

    async def add_witness(
        self,
        ceremony_id: str,
        witness_id: str,
        signature: bytes,
        witness_type: WitnessType = WitnessType.KEEPER,
    ) -> KeyGenerationCeremony:
        """Add a witness attestation to a ceremony (CT-12).

        Adds the witness signature and auto-transitions to APPROVED
        when REQUIRED_WITNESSES threshold is met.

        Args:
            ceremony_id: The ceremony UUID as string.
            witness_id: ID of the witness (e.g., "KEEPER:alice").
            signature: Ed25519 signature proving attestation.
            witness_type: Type of witness (default: KEEPER).

        Returns:
            Updated KeyGenerationCeremony.

        Raises:
            WriteBlockedDuringHaltError: If system is halted.
            CeremonyNotFoundError: If ceremony doesn't exist.
            DuplicateWitnessError: If witness already signed.
            InvalidCeremonyStateError: If not in PENDING state.
        """
        log = logger.bind(
            operation="add_witness",
            ceremony_id=ceremony_id,
            witness_id=witness_id,
        )

        # CT-11: HALT CHECK FIRST
        if self._halt_guard:
            await self._halt_guard.check_write_allowed()

        # Get ceremony
        ceremony = await self._ceremony_repo.get_ceremony(ceremony_id)
        if ceremony is None:
            log.warning("ceremony_not_found", message="FR69: Ceremony not found")
            raise CeremonyNotFoundError(f"FR69: Ceremony not found: {ceremony_id}")

        # Verify state allows witnessing
        if ceremony.state != CeremonyState.PENDING:
            log.warning(
                "invalid_state_for_witnessing",
                current_state=ceremony.state.value,
            )
            raise InvalidCeremonyStateError(
                f"FP-4: Cannot add witness in {ceremony.state.value} state"
            )

        # Check for duplicate witness
        if ceremony.has_witness(witness_id):
            log.warning(
                "duplicate_witness",
                message="CT-12: Witness has already signed",
            )
            raise DuplicateWitnessError(
                f"CT-12: Witness {witness_id} has already signed this ceremony"
            )

        # CT-12: Verify witness signature cryptographically
        # Build the content the witness should have signed (ceremony attestation)
        witness_content = f"{ceremony_id}:{witness_id}:{ceremony.keeper_id}".encode()

        # Try to get witness key from registry and verify
        witness_key = await self._key_registry.get_active_key_for_keeper(witness_id)
        if witness_key:
            # Verify signature with witness's registered key
            is_valid = await self._hsm.verify_with_key(
                content=witness_content,
                signature=signature,
                key_id=witness_key.key_id,
            )
            if not is_valid:
                log.warning(
                    "invalid_witness_signature",
                    witness_id=witness_id,
                    message="CT-12: Witness signature verification failed",
                )
                raise InvalidWitnessSignatureError(
                    f"CT-12: Invalid signature from witness {witness_id}"
                )
            log.debug(
                "witness_signature_verified",
                witness_id=witness_id,
            )
        else:
            # H2 Security Fix: Validate bootstrap mode before accepting unverified witness
            # If bootstrap mode is disabled, this will raise BootstrapModeDisabledError
            validate_bootstrap_mode_for_unverified_witness(witness_id)

            # Bootstrap mode is enabled - log warning and write event for auditability
            log.warning(
                "witness_key_not_found_bootstrap_mode",
                witness_id=witness_id,
                bootstrap_enabled=is_witness_bootstrap_enabled(),
                message="H2/CT-12: Witness key not found - accepted in bootstrap mode (unverified)",
            )

            # Write event for unverified witness (not just warning log) - H2 fix
            if self._event_writer:
                await self._event_writer.write_event(
                    event_type="ceremony.unverified_witness_accepted",
                    payload={
                        "ceremony_id": str(ceremony.id),
                        "witness_id": witness_id,
                        "keeper_id": ceremony.keeper_id,
                        "bootstrap_mode_enabled": True,
                        "security_finding": "H2",
                        "warning": "Witness signature not cryptographically verified - bootstrap mode",
                    },
                    agent_id="SYSTEM:ceremony_service",
                )

        # Create witness
        witness = CeremonyWitness(
            witness_id=witness_id,
            signature=signature,
            witness_type=witness_type,
        )

        # Add witness
        await self._ceremony_repo.add_witness(ceremony_id, witness)

        # Get updated ceremony
        ceremony = await self._ceremony_repo.get_ceremony(ceremony_id)
        if ceremony is None:
            raise CeremonyNotFoundError(f"FR69: Ceremony not found: {ceremony_id}")

        log.info(
            "witness_added",
            witness_count=len(ceremony.witnesses),
            required=REQUIRED_WITNESSES,
        )

        # Write witnessed event
        if self._event_writer:
            payload = KeyGenerationCeremonyWitnessedPayload(
                ceremony_id=ceremony.id,
                keeper_id=ceremony.keeper_id,
                witness_id=witness_id,
                witness_type=witness_type.value,
                witness_count=len(ceremony.witnesses),
            )
            await self._event_writer.write_event(
                event_type=KEY_GENERATION_CEREMONY_WITNESSED_EVENT_TYPE,
                payload=payload.to_dict(),
                agent_id="SYSTEM:ceremony_service",
            )

        # Auto-transition to APPROVED if threshold met
        if ceremony.has_sufficient_witnesses():
            log.info(
                "ceremony_auto_approved",
                witness_count=len(ceremony.witnesses),
                message="Ceremony auto-approved with sufficient witnesses",
            )
            await self._ceremony_repo.update_state(ceremony_id, CeremonyState.APPROVED)
            ceremony = await self._ceremony_repo.get_ceremony(ceremony_id)
            if ceremony is None:
                raise CeremonyNotFoundError(f"FR69: Ceremony not found: {ceremony_id}")

        return ceremony

    async def execute_ceremony(
        self,
        ceremony_id: str,
    ) -> KeyGenerationCeremony:
        """Execute an approved ceremony and register the new key (FR69).

        Generates the new key via HSM, registers it in the key registry,
        and handles transition period for rotations (ADR-4).

        Args:
            ceremony_id: The ceremony UUID as string.

        Returns:
            Updated KeyGenerationCeremony with new_key_id set.

        Raises:
            WriteBlockedDuringHaltError: If system is halted.
            CeremonyNotFoundError: If ceremony doesn't exist.
            InvalidCeremonyStateError: If not in APPROVED state.
            InsufficientWitnessesError: If not enough witnesses.
        """
        log = logger.bind(
            operation="execute_ceremony",
            ceremony_id=ceremony_id,
        )

        # CT-11: HALT CHECK FIRST
        if self._halt_guard:
            await self._halt_guard.check_write_allowed()

        # Get ceremony
        ceremony = await self._ceremony_repo.get_ceremony(ceremony_id)
        if ceremony is None:
            log.warning("ceremony_not_found", message="FR69: Ceremony not found")
            raise CeremonyNotFoundError(f"FR69: Ceremony not found: {ceremony_id}")

        # Verify state allows execution
        if ceremony.state != CeremonyState.APPROVED:
            log.warning(
                "invalid_state_for_execution",
                current_state=ceremony.state.value,
            )
            raise InvalidCeremonyStateError(
                f"FP-4: Cannot execute in {ceremony.state.value} state"
            )

        # Verify sufficient witnesses (CT-12)
        if not ceremony.has_sufficient_witnesses():
            log.warning(
                "insufficient_witnesses",
                witness_count=len(ceremony.witnesses),
                required=REQUIRED_WITNESSES,
            )
            raise InsufficientWitnessesError(
                f"CT-12: Ceremony requires {REQUIRED_WITNESSES} witnesses, "
                f"got {len(ceremony.witnesses)}"
            )

        # Transition to EXECUTING
        await self._ceremony_repo.update_state(ceremony_id, CeremonyState.EXECUTING)

        try:
            # ADR-4: Validate and log HSM mode before key generation
            hsm_mode = await self._hsm.get_mode()
            log.info(
                "hsm_mode_validated",
                hsm_mode=hsm_mode.value,
                ceremony_id=ceremony_id,
                message=f"FR69: Key generation using {hsm_mode.value} HSM",
            )

            # Generate new key via HSM (FR69: actual HSM key generation)
            new_key_id = await self._hsm.generate_key_pair()

            # Get the public key bytes from HSM
            public_key_bytes = await self._hsm.get_public_key_bytes(new_key_id)

            now = datetime.now(timezone.utc)

            new_key = KeeperKey(
                id=uuid4(),
                keeper_id=ceremony.keeper_id,
                key_id=new_key_id,
                public_key=public_key_bytes,
                active_from=now,
                active_until=None,  # Currently active
                created_at=now,
            )

            # Register new key
            await self._key_registry.register_key(new_key)

            # Calculate transition period for rotations
            transition_end_at: datetime | None = None
            if (
                ceremony.ceremony_type == CeremonyType.KEY_ROTATION
                and ceremony.old_key_id
            ):
                transition_end_at = now + timedelta(days=TRANSITION_PERIOD_DAYS)

                # Deactivate old key at end of transition period
                await self._key_registry.deactivate_key(
                    ceremony.old_key_id,
                    transition_end_at,
                )

                log.info(
                    "key_rotation_transition_started",
                    old_key_id=ceremony.old_key_id,
                    new_key_id=new_key_id,
                    transition_end_at=transition_end_at.isoformat(),
                    message="ADR-4: Both keys valid during 30-day transition",
                )

            # Mark ceremony completed
            await self._ceremony_repo.mark_completed(
                ceremony_id=ceremony_id,
                new_key_id=new_key_id,
                transition_end_at=transition_end_at,
            )

            # Get final ceremony state
            ceremony = await self._ceremony_repo.get_ceremony(ceremony_id)
            if ceremony is None:
                raise CeremonyNotFoundError(f"FR69: Ceremony not found: {ceremony_id}")

            log.info(
                "ceremony_completed",
                new_key_id=new_key_id,
                message="Key generation ceremony completed successfully",
            )

            # Write completed event
            if self._event_writer:
                payload = KeyGenerationCeremonyCompletedPayload(
                    ceremony_id=ceremony.id,
                    keeper_id=ceremony.keeper_id,
                    ceremony_type=ceremony.ceremony_type.value,
                    new_key_id=new_key_id,
                    old_key_id=ceremony.old_key_id,
                    transition_end_at=transition_end_at,
                    witness_ids=tuple(ceremony.get_witness_ids()),
                )
                await self._event_writer.write_event(
                    event_type=KEY_GENERATION_CEREMONY_COMPLETED_EVENT_TYPE,
                    payload=payload.to_dict(),
                    agent_id="SYSTEM:ceremony_service",
                )

            return ceremony

        except Exception as e:
            # Transition to FAILED on any error
            log.error(
                "ceremony_execution_failed",
                error=str(e),
            )
            await self._ceremony_repo.update_state(
                ceremony_id,
                CeremonyState.FAILED,
                failure_reason=str(e),
            )
            raise

    async def check_ceremony_timeout(self) -> list[KeyGenerationCeremony]:
        """Check for timed out ceremonies (VAL-2).

        Background task that finds and expires ceremonies exceeding
        CEREMONY_TIMEOUT_SECONDS. Uses EXPIRED state (distinct from FAILED)
        to indicate timeout vs. error conditions.

        Returns:
            List of ceremonies that were expired due to timeout.
        """
        log = logger.bind(operation="check_ceremony_timeout")

        # Calculate timeout threshold
        threshold = datetime.now(timezone.utc) - timedelta(seconds=CEREMONY_TIMEOUT_SECONDS)

        # Get timed out ceremonies
        timed_out = await self._ceremony_repo.get_timed_out_ceremonies(threshold)

        expired_ceremonies: list[KeyGenerationCeremony] = []

        for ceremony in timed_out:
            log.warning(
                "ceremony_timeout",
                ceremony_id=str(ceremony.id),
                keeper_id=ceremony.keeper_id,
                created_at=ceremony.created_at.isoformat(),
                message="VAL-2: Ceremony timed out",
            )

            # Transition to EXPIRED (timeout is different from FAILED/error)
            reason = f"VAL-2: Ceremony timeout after {CEREMONY_TIMEOUT_SECONDS}s"
            await self._ceremony_repo.update_state(
                str(ceremony.id),
                CeremonyState.EXPIRED,
                failure_reason=reason,
            )

            # Write failed event (expired is a type of failure for event purposes)
            if self._event_writer:
                payload = KeyGenerationCeremonyFailedPayload(
                    ceremony_id=ceremony.id,
                    keeper_id=ceremony.keeper_id,
                    ceremony_type=ceremony.ceremony_type.value,
                    failure_reason=reason,
                    witness_count=len(ceremony.witnesses),
                )
                await self._event_writer.write_event(
                    event_type=KEY_GENERATION_CEREMONY_FAILED_EVENT_TYPE,
                    payload=payload.to_dict(),
                    agent_id="SYSTEM:ceremony_service",
                )

            # Get updated ceremony
            updated = await self._ceremony_repo.get_ceremony(str(ceremony.id))
            if updated:
                expired_ceremonies.append(updated)

        return expired_ceremonies

    async def get_ceremony(self, ceremony_id: str) -> KeyGenerationCeremony | None:
        """Get a ceremony by ID.

        Args:
            ceremony_id: The ceremony UUID as string.

        Returns:
            KeyGenerationCeremony if found, None otherwise.
        """
        return await self._ceremony_repo.get_ceremony(ceremony_id)

    async def get_active_ceremonies(self) -> list[KeyGenerationCeremony]:
        """Get all active ceremonies.

        Returns:
            List of active (non-terminal) ceremonies.
        """
        return await self._ceremony_repo.get_active_ceremonies()

    # H3 Security Fix: Emergency Key Revocation

    async def emergency_revoke_key(
        self,
        key_id: str,
        reason: str,
        revoked_by: str,
    ) -> datetime:
        """Emergency revoke a key immediately, bypassing transition period (H3 fix).

        This method provides IMMEDIATE key revocation for compromised keys,
        bypassing the normal 30-day transition window. Use only when a key
        is known or suspected to be compromised.

        H3 Security Finding:
        - Normal key rotation has 30-day transition where both keys are valid
        - If a key is compromised, attacker has 30 days to use it
        - This method allows immediate revocation for compromised keys

        HALT CHECK is performed first per CT-11.

        Args:
            key_id: The HSM key ID to immediately revoke.
            reason: The reason for emergency revocation (e.g., "Key compromised").
            revoked_by: Who initiated the revocation (e.g., "KEEPER:admin").

        Returns:
            The datetime when the key was revoked (for audit trail).

        Raises:
            WriteBlockedDuringHaltError: If system is halted.
            KeyError: If key_id doesn't exist.
        """
        log = logger.bind(
            operation="emergency_revoke_key",
            key_id=key_id,
            reason=reason,
            revoked_by=revoked_by,
        )

        # CT-11: HALT CHECK FIRST
        if self._halt_guard:
            await self._halt_guard.check_write_allowed()

        log.critical(
            "emergency_key_revocation_initiated",
            message="H3: Emergency key revocation requested",
        )

        # Perform immediate revocation via registry
        revoked_at = await self._key_registry.emergency_revoke_key(
            key_id=key_id,
            reason=reason,
            revoked_by=revoked_by,
        )

        log.critical(
            "emergency_key_revocation_completed",
            revoked_at=revoked_at.isoformat(),
            message="H3: Key immediately revoked - bypassing 30-day transition",
        )

        # Write emergency revocation event for audit trail
        if self._event_writer:
            await self._event_writer.write_event(
                event_type="key.emergency_revoked",
                payload={
                    "key_id": key_id,
                    "reason": reason,
                    "revoked_by": revoked_by,
                    "revoked_at": revoked_at.isoformat(),
                    "security_finding": "H3",
                    "bypass_transition_period": True,
                    "warning": "Key immediately revoked due to suspected compromise",
                },
                agent_id="SYSTEM:ceremony_service",
            )

        return revoked_at
