"""ContextBundleService application service (Story 2.9, ADR-2).

This service orchestrates context bundle creation and validation
for agent deliberation contexts.

ADR-2 Requirements:
- Context bundles provide deterministic state for stateless agents
- Bundles must be signed at creation time
- Receivers verify signature BEFORE parsing/using bundle
- as_of_event_seq anchors bundle to specific event for reproducibility

Constitutional Constraints:
- CT-1: LLMs are stateless -> Context bundles provide deterministic state
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Bundle hash creates audit trail
- CT-13: Integrity outranks availability -> Signature verification mandatory

Architecture Pattern:
    ContextBundleService orchestrates ADR-2 compliance:

    create_bundle_for_meeting(input):
      ├─ halt_checker.is_halted()           # HALT FIRST rule
      ├─ event_store.get_max_sequence()     # Get as_of_event_seq
      ├─ creator.create_bundle()            # Create signed bundle
      └─ Return bundle with hash

    validate_bundle(bundle):
      ├─ halt_checker.is_halted()           # HALT FIRST rule
      ├─ validator.validate_signature()     # ADR-2: Signature FIRST
      ├─ validator.validate_schema()        # Schema validation
      └─ validator.validate_freshness()     # as_of_event_seq check
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import structlog

from src.application.ports.context_bundle_creator import (
    BundleCreationResult,
    ContextBundleCreatorPort,
)
from src.application.ports.context_bundle_validator import (
    BundleValidationResult,
    ContextBundleValidatorPort,
)
from src.application.ports.event_store import EventStorePort
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.context_bundle import (
    ContentRef,
    ContextBundlePayload,
)

logger = structlog.get_logger()


@dataclass(frozen=True)
class CreateBundleInput:
    """Input for creating a context bundle.

    Attributes:
        meeting_id: UUID of the meeting for this bundle.
        identity_prompt_ref: ContentRef to agent identity prompt.
        meeting_state_ref: ContentRef to meeting state snapshot.
        precedent_refs: Tuple of ContentRefs to relevant precedents.
    """

    meeting_id: UUID
    identity_prompt_ref: ContentRef
    meeting_state_ref: ContentRef
    precedent_refs: tuple[ContentRef, ...] = ()


@dataclass(frozen=True)
class CreateBundleOutput:
    """Output from creating a context bundle.

    Attributes:
        success: Whether creation succeeded.
        bundle: The created bundle if successful.
        bundle_hash: The computed hash of the bundle.
        error_message: Error message if creation failed.
    """

    success: bool
    bundle: ContextBundlePayload | None = None
    bundle_hash: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ValidateBundleOutput:
    """Output from validating a context bundle.

    Attributes:
        valid: Whether the bundle passed all validations.
        bundle_id: ID of the validated bundle.
        error_code: Error code if validation failed.
        error_message: Error message if validation failed.
    """

    valid: bool
    bundle_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class ContextBundleService:
    """Application service for context bundle operations (ADR-2).

    This service provides the primary interface for:
    - Creating context bundles for meetings (MA-3 pattern)
    - Validating context bundles (ADR-2 requirements)
    - Getting current head sequence for as_of_event_seq

    HALT FIRST Rule:
        Every operation checks halt state before proceeding.
        Never retry after SystemHaltedError.

    MA-3: Temporal Determinism:
        Bundles are anchored to a specific sequence number (as_of_event_seq)
        to ensure reproducibility. "Latest" is non-deterministic.

    Attributes:
        _halt_checker: Interface for checking halt state.
        _creator: Interface for bundle creation.
        _validator: Interface for bundle validation.
        _event_store: Interface for event store operations.
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        creator: ContextBundleCreatorPort,
        validator: ContextBundleValidatorPort,
        event_store: EventStorePort,
    ) -> None:
        """Initialize the service with required dependencies.

        Args:
            halt_checker: Interface for checking halt state.
            creator: Interface for bundle creation.
            validator: Interface for bundle validation.
            event_store: Interface for event store operations.

        Raises:
            TypeError: If any required dependency is None.
        """
        if halt_checker is None:
            raise TypeError("halt_checker is required")
        if creator is None:
            raise TypeError("creator is required")
        if validator is None:
            raise TypeError("validator is required")
        if event_store is None:
            raise TypeError("event_store is required")

        self._halt_checker = halt_checker
        self._creator = creator
        self._validator = validator
        self._event_store = event_store

    async def create_bundle_for_meeting(
        self,
        input_data: CreateBundleInput,
    ) -> CreateBundleOutput:
        """Create a signed context bundle for a meeting (ADR-2).

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Get current head sequence (as_of_event_seq)
            3. Create signed bundle via creator
            4. Return bundle with hash

        MA-3 Pattern: The bundle is anchored to the current head sequence,
        making the context deterministic and reproducible.

        Args:
            input_data: The bundle creation input data.

        Returns:
            CreateBundleOutput with the created bundle.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "bundle_creation_blocked_halted",
                meeting_id=str(input_data.meeting_id),
            )
            raise SystemHaltedError("System halted - cannot create context bundle")

        # Get current head sequence for as_of_event_seq (MA-3)
        as_of_event_seq = await self._event_store.get_max_sequence()

        # If store is empty, use 1 as starting sequence
        if as_of_event_seq == 0:
            as_of_event_seq = 1

        # Create the signed bundle
        creation_result: BundleCreationResult = await self._creator.create_bundle(
            meeting_id=input_data.meeting_id,
            as_of_event_seq=as_of_event_seq,
            identity_prompt_ref=input_data.identity_prompt_ref,
            meeting_state_ref=input_data.meeting_state_ref,
            precedent_refs=input_data.precedent_refs,
        )

        if not creation_result.success:
            logger.error(
                "bundle_creation_failed",
                meeting_id=str(input_data.meeting_id),
                error=creation_result.error_message,
            )
            return CreateBundleOutput(
                success=False,
                error_message=creation_result.error_message,
            )

        # success=True guarantees bundle and bundle_hash are non-None
        assert creation_result.bundle is not None
        assert creation_result.bundle_hash is not None

        logger.info(
            "context_bundle_created",
            bundle_id=creation_result.bundle.bundle_id,
            meeting_id=str(input_data.meeting_id),
            as_of_event_seq=as_of_event_seq,
            bundle_hash_prefix=creation_result.bundle_hash[:8],
            precedent_count=len(input_data.precedent_refs),
        )

        return CreateBundleOutput(
            success=True,
            bundle=creation_result.bundle,
            bundle_hash=creation_result.bundle_hash,
        )

    async def validate_bundle(
        self,
        bundle: ContextBundlePayload,
    ) -> ValidateBundleOutput:
        """Validate a context bundle (ADR-2).

        ADR-2 Critical: Signature is verified BEFORE parsing/using content.

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Get current head sequence for freshness check
            3. Run validate_all (signature first, then schema, then freshness)
            4. Return validation result

        Args:
            bundle: The bundle to validate.

        Returns:
            ValidateBundleOutput with validation result.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "bundle_validation_blocked_halted",
                bundle_id=bundle.bundle_id if bundle else "unknown",
            )
            raise SystemHaltedError("System halted - cannot validate context bundle")

        # Get current head sequence for freshness check
        current_head_seq = await self._event_store.get_max_sequence()

        # Use 1 if store is empty
        if current_head_seq == 0:
            current_head_seq = 1

        # Run all validations (signature first per ADR-2)
        validation_result: BundleValidationResult = await self._validator.validate_all(
            bundle=bundle,
            current_head_seq=current_head_seq,
        )

        if validation_result.valid:
            logger.debug(
                "bundle_validation_passed",
                bundle_id=bundle.bundle_id,
                as_of_event_seq=bundle.as_of_event_seq,
            )
        else:
            logger.warning(
                "bundle_validation_failed",
                bundle_id=bundle.bundle_id,
                error_code=validation_result.error_code,
                error_message=validation_result.error_message,
            )

        return ValidateBundleOutput(
            valid=validation_result.valid,
            bundle_id=validation_result.bundle_id,
            error_code=validation_result.error_code,
            error_message=validation_result.error_message,
        )

    async def get_current_head_seq(self) -> int:
        """Get the current head sequence number.

        Used to determine the as_of_event_seq for new bundles.
        Per MA-3, bundles are anchored to specific sequence numbers
        for determinism.

        Returns:
            The current maximum sequence number (1 if store is empty).

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT FIRST
        if await self._halt_checker.is_halted():
            logger.warning("head_seq_query_blocked_halted")
            raise SystemHaltedError("System halted - cannot query head sequence")

        max_seq = await self._event_store.get_max_sequence()

        # Return 1 if store is empty (valid starting sequence)
        return max_seq if max_seq > 0 else 1

    async def get_bundle(
        self,
        bundle_id: str,
    ) -> ContextBundlePayload | None:
        """Get a stored bundle by ID.

        Args:
            bundle_id: The bundle ID to lookup.

        Returns:
            The ContextBundlePayload if found, None otherwise.
        """
        return await self._creator.get_bundle(bundle_id)

    async def verify_bundle_signature(
        self,
        bundle: ContextBundlePayload,
    ) -> bool:
        """Verify a bundle's signature only.

        ADR-2: Signature verification is the first and most critical check.

        Args:
            bundle: The bundle to verify.

        Returns:
            True if signature is valid, False otherwise.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT FIRST
        if await self._halt_checker.is_halted():
            logger.warning(
                "signature_verification_blocked_halted",
                bundle_id=bundle.bundle_id if bundle else "unknown",
            )
            raise SystemHaltedError("System halted - cannot verify signature")

        result = await self._validator.validate_signature(bundle)
        return result.valid
