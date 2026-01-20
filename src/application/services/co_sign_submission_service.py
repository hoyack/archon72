"""Co-sign submission service implementation (Story 5.2, Story 5.3, Story 5.4, Story 5.5, Story 5.6, FR-6.1, FR-6.4, FR-6.5, FR-6.6, FR-5.1, FR-5.3).

This module implements the CoSignSubmissionProtocol for submitting
co-signatures on petitions in the Three Fates system.

Constitutional Constraints:
- FR-6.1: Seeker SHALL be able to co-sign active petition
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id)
- FR-6.3: System SHALL reject co-sign after fate assignment
- FR-6.4: System SHALL increment co-signer count atomically
- FR-6.5: System SHALL check escalation threshold on each co-sign
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co_signer_count [P0]
- NFR-5.1: Rate limiting per identity: Configurable per type
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- CT-11: Silent failure destroys legitimacy - return 429, never silently drop
- CT-12: Every action that affects a petition must be witnessed
- CT-13: Halt rejects writes, allows reads
- CT-14: Silence must be expensive - auto-escalation ensures collective petitions get King attention
- NFR-3.5: 0 duplicate signatures ever exist
- NFR-1.3: Response latency < 150ms p99
- NFR-1.4: Threshold detection latency < 1 second
- SYBIL-1: Identity verification + rate limiting per verified identity
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.auto_escalation_executor import (
    AutoEscalationExecutorProtocol,
)
from src.application.ports.co_sign_rate_limiter import CoSignRateLimiterProtocol
from src.application.ports.co_sign_submission import CoSignSubmissionResult
from src.application.ports.escalation_threshold import (
    EscalationThresholdCheckerProtocol,
)
from src.application.ports.identity_verification import (
    IdentityStatus,
    IdentityStoreProtocol,
)
from src.domain.errors import (
    AlreadySignedError,
    CoSignPetitionFatedError,
    CoSignPetitionNotFoundError,
    CoSignRateLimitExceededError,
    IdentityNotFoundError,
    IdentityServiceUnavailableError,
    IdentitySuspendedError,
    SystemHaltedError,
)
from src.domain.events import CoSignRecordedEvent
from src.domain.models.co_sign import CoSign

if TYPE_CHECKING:
    from src.application.ports.co_sign_submission import CoSignRepositoryProtocol
    from src.application.ports.halt import HaltChecker
    from src.application.ports.petition_submission_repository import (
        PetitionSubmissionRepositoryProtocol,
    )

logger = get_logger(__name__)


class CoSignSubmissionService:
    """Service for submitting co-signatures on petitions (Story 5.2, Story 5.3, Story 5.4, Story 5.5, Story 5.6).

    Implements the co-sign submission flow for Seekers supporting petitions
    in the Three Fates system.

    The service ensures:
    1. System is not in halt state (CT-13)
    2. Signer identity is verified (NFR-5.2, LEGIT-1)
    3. Rate limit is checked (FR-6.6, SYBIL-1)
    4. Petition exists (FR-6.1)
    5. Petition is not in terminal state (FR-6.3)
    6. Signer has not already co-signed (FR-6.2, NFR-3.5)
    7. Count increment is atomic (FR-6.4)
    8. Rate limit counter is incremented after success (FR-6.6)
    9. Escalation threshold is checked (FR-6.5)
    10. Auto-escalation is executed if threshold reached (FR-5.1, FR-5.3)
    11. Co-sign is witnessed with identity_verified=True (CT-12)

    Example:
        >>> service = CoSignSubmissionService(
        ...     co_sign_repo=co_sign_repo,
        ...     petition_repo=petition_repo,
        ...     halt_checker=halt_checker,
        ...     identity_store=identity_store,
        ...     rate_limiter=rate_limiter,
        ...     threshold_checker=threshold_checker,
        ...     auto_escalation_executor=auto_escalation_executor,
        ... )
        >>> result = await service.submit_co_sign(
        ...     petition_id=petition_id,
        ...     signer_id=signer_id,
        ... )
    """

    def __init__(
        self,
        co_sign_repo: CoSignRepositoryProtocol,
        petition_repo: PetitionSubmissionRepositoryProtocol,
        halt_checker: HaltChecker,
        identity_store: IdentityStoreProtocol | None = None,
        rate_limiter: CoSignRateLimiterProtocol | None = None,
        threshold_checker: EscalationThresholdCheckerProtocol | None = None,
        auto_escalation_executor: AutoEscalationExecutorProtocol | None = None,
    ) -> None:
        """Initialize the co-sign submission service.

        Args:
            co_sign_repo: Repository for co-sign persistence.
            petition_repo: Repository for petition access.
            halt_checker: Service for checking halt state.
            identity_store: Optional identity verification store (NFR-5.2).
                           If not provided, identity verification is skipped.
            rate_limiter: Optional rate limiter for SYBIL-1 (FR-6.6).
                         If not provided, rate limiting is skipped.
            threshold_checker: Optional threshold checker for escalation (FR-6.5).
                              If not provided, threshold checking is skipped.
            auto_escalation_executor: Optional executor for auto-escalation (FR-5.1).
                                     If not provided, auto-escalation is skipped.
        """
        self._co_sign_repo = co_sign_repo
        self._petition_repo = petition_repo
        self._halt_checker = halt_checker
        self._identity_store = identity_store
        self._rate_limiter = rate_limiter
        self._threshold_checker = threshold_checker
        self._auto_escalation_executor = auto_escalation_executor

    async def submit_co_sign(
        self,
        petition_id: UUID,
        signer_id: UUID,
    ) -> CoSignSubmissionResult:
        """Submit a co-signature on a petition.

        This is the main entry point for co-signing a petition.
        The method is atomic - either the co-sign completes fully
        (record + count increment + event) or not at all.

        Args:
            petition_id: The petition to co-sign.
            signer_id: The Seeker adding their support.

        Returns:
            CoSignSubmissionResult with the created co-sign details,
            updated co_signer_count, rate limit info, and threshold info.

        Raises:
            SystemHaltedError: System is in halt state (CT-13)
            IdentityNotFoundError: Signer identity not found (NFR-5.2)
            IdentitySuspendedError: Signer identity suspended (NFR-5.2)
            IdentityServiceUnavailableError: Identity service unavailable (NFR-5.2)
            CoSignRateLimitExceededError: Rate limit exceeded (FR-6.6, SYBIL-1)
            CoSignPetitionNotFoundError: Petition doesn't exist
            CoSignPetitionFatedError: Petition in terminal state (FR-6.3)
            AlreadySignedError: Signer already co-signed (FR-6.2, NFR-3.5)
        """
        log = logger.bind(
            petition_id=str(petition_id),
            signer_id=str(signer_id),
        )
        log.info("Starting co-sign submission")

        # Step 1: HALT CHECK FIRST (CT-13)
        # Co-signing is a write operation, reject during halt
        if await self._halt_checker.is_halted():
            log.warning("Co-sign rejected due to system halt")
            raise SystemHaltedError(
                "Co-sign operations are not permitted during system halt"
            )

        # Step 2: IDENTITY VERIFICATION (NFR-5.2, LEGIT-1)
        # Verify signer identity before any database writes
        identity_verified = False
        if self._identity_store is not None:
            verification_result = self._identity_store.verify(signer_id)
            log.debug(
                "Identity verification result",
                status=verification_result.status.value,
            )

            if verification_result.status == IdentityStatus.NOT_FOUND:
                log.warning("Co-sign rejected - identity not found")
                raise IdentityNotFoundError(signer_id)

            if verification_result.status == IdentityStatus.SUSPENDED:
                log.warning(
                    "Co-sign rejected - identity suspended",
                    reason=verification_result.suspension_reason,
                )
                raise IdentitySuspendedError(
                    signer_id,
                    reason=verification_result.suspension_reason,
                )

            if verification_result.status == IdentityStatus.SERVICE_UNAVAILABLE:
                log.warning("Co-sign rejected - identity service unavailable")
                raise IdentityServiceUnavailableError(signer_id)

            # Identity is valid
            identity_verified = verification_result.is_valid
            log.debug(
                "Identity verified successfully", identity_verified=identity_verified
            )

        # Step 3: RATE LIMIT CHECK (FR-6.6, SYBIL-1, CT-11)
        # Check rate limit AFTER identity verification, BEFORE petition check
        # Per AC3: Rate limit checked after identity verification, before duplicate check
        rate_limit_remaining: int | None = None
        rate_limit_reset_at: datetime | None = None
        if self._rate_limiter is not None:
            rate_result = await self._rate_limiter.check_rate_limit(signer_id)
            log.debug(
                "Rate limit check result",
                allowed=rate_result.allowed,
                remaining=rate_result.remaining,
                current_count=rate_result.current_count,
                limit=rate_result.limit,
            )

            if not rate_result.allowed:
                # Calculate retry_after_seconds from reset_at
                now = datetime.now(timezone.utc)
                retry_after_seconds = max(
                    1,
                    int((rate_result.reset_at - now).total_seconds()),
                )
                log.warning(
                    "Co-sign rejected due to rate limit exceeded",
                    current_count=rate_result.current_count,
                    limit=rate_result.limit,
                    reset_at=rate_result.reset_at.isoformat(),
                    retry_after_seconds=retry_after_seconds,
                )
                raise CoSignRateLimitExceededError(
                    signer_id=signer_id,
                    current_count=rate_result.current_count,
                    limit=rate_result.limit,
                    reset_at=rate_result.reset_at,
                    retry_after_seconds=retry_after_seconds,
                )

            # Store rate limit info for response (AC6)
            rate_limit_remaining = rate_result.remaining
            rate_limit_reset_at = rate_result.reset_at

        # Step 4: Verify petition exists
        petition = await self._petition_repo.get(petition_id)
        if petition is None:
            log.warning("Petition not found")
            raise CoSignPetitionNotFoundError(petition_id)

        # Store petition type for threshold check and response
        petition_type = petition.type

        # Step 5: Verify petition is not in terminal state (FR-6.3)
        if petition.state.is_terminal():
            log.warning(
                "Co-sign rejected - petition already fated",
                terminal_state=petition.state.value,
            )
            raise CoSignPetitionFatedError(petition_id, petition.state.value)

        # Step 6: Check for duplicate co-sign (FR-6.2, NFR-3.5)
        # Note: Database constraint is the ultimate guard, but we check first
        # to provide better error messages and avoid unnecessary work
        # Story 5.7: Enhanced error with existing signature details
        existing_signature = await self._co_sign_repo.get_existing(
            petition_id, signer_id
        )
        if existing_signature is not None:
            existing_cosign_id, existing_signed_at = existing_signature
            # LEGIT-1: Log duplicate attempt with pattern data for fraud analysis
            log.info(
                "duplicate_co_sign_attempt",
                message="LEGIT-1: Duplicate co-sign attempt detected",
                existing_cosign_id=str(existing_cosign_id),
                existing_signed_at=existing_signed_at.isoformat(),
                petition_id=str(petition_id),
                signer_id=str(signer_id),
                detection_method="pre_persistence_check",
            )
            raise AlreadySignedError(
                petition_id=petition_id,
                signer_id=signer_id,
                existing_cosign_id=existing_cosign_id,
                signed_at=existing_signed_at,
            )

        # Step 7: Generate co-sign data
        cosign_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        # Step 8: Persist co-sign and increment count atomically (FR-6.4)
        # The repository handles atomic increment
        try:
            new_count = await self._co_sign_repo.create(
                cosign_id=cosign_id,
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=signed_at,
                content_hash=content_hash,
                identity_verified=identity_verified,
            )
        except AlreadySignedError as e:
            # Race condition - signer submitted while we were processing
            # LEGIT-1: Log duplicate attempt caught by database constraint
            # This indicates a potential race condition or rapid retry pattern
            log.warning(
                "duplicate_co_sign_constraint_violation",
                message="LEGIT-1: Duplicate co-sign caught by database constraint (race condition)",
                petition_id=str(petition_id),
                signer_id=str(signer_id),
                detection_method="database_constraint",
                existing_cosign_id=str(e.existing_cosign_id)
                if e.existing_cosign_id
                else None,
                existing_signed_at=e.signed_at.isoformat() if e.signed_at else None,
            )
            raise

        # Step 9: Record co-sign for rate limiting (FR-6.6, AC4)
        # CRITICAL: Record AFTER successful persistence, not before
        # Per AC4: Rate limit counter incremented AFTER successful persistence
        if self._rate_limiter is not None:
            await self._rate_limiter.record_co_sign(signer_id)
            # Update remaining count after recording
            rate_limit_remaining = (
                rate_limit_remaining - 1 if rate_limit_remaining is not None else None
            )
            log.debug(
                "Rate limit counter incremented",
                rate_limit_remaining=rate_limit_remaining,
            )

        # Step 10: THRESHOLD CHECK (FR-6.5, Story 5.5)
        # Check escalation threshold AFTER persistence, BEFORE event emission
        # Per AC4 of Story 5.5: threshold check occurs AFTER co-sign persistence
        threshold_reached = False
        threshold_value: int | None = None
        if self._threshold_checker is not None:
            threshold_result = self._threshold_checker.check_threshold(
                petition_type=petition_type,
                co_signer_count=new_count,
            )
            threshold_reached = threshold_result.threshold_reached
            threshold_value = threshold_result.threshold_value

            if threshold_reached:
                log.info(
                    "Escalation threshold reached",
                    petition_type=petition_type.value,
                    threshold=threshold_value,
                    co_signer_count=new_count,
                )
            else:
                log.debug(
                    "Threshold check complete",
                    petition_type=petition_type.value,
                    threshold=threshold_value,
                    co_signer_count=new_count,
                    threshold_reached=False,
                )

        # Step 11: AUTO-ESCALATION EXECUTION (FR-5.1, FR-5.3, Story 5.6)
        # Execute auto-escalation when threshold is reached
        # Per AC6 of Story 5.6: auto-escalation executes synchronously (same request)
        escalation_triggered = False
        escalation_id: UUID | None = None
        if threshold_reached and self._auto_escalation_executor is not None:
            try:
                escalation_result = await self._auto_escalation_executor.execute(
                    petition_id=petition_id,
                    trigger_type="CO_SIGNER_THRESHOLD",
                    co_signer_count=new_count,
                    threshold=threshold_value or 0,
                    triggered_by=signer_id,
                )
                escalation_triggered = escalation_result.triggered
                escalation_id = escalation_result.escalation_id

                if escalation_triggered:
                    log.info(
                        "Auto-escalation executed successfully",
                        petition_id=str(petition_id),
                        escalation_id=str(escalation_id),
                        petition_type=petition_type.value,
                        co_signer_count=new_count,
                    )
                elif escalation_result.already_escalated:
                    log.info(
                        "Petition already escalated, no duplicate escalation",
                        petition_id=str(petition_id),
                        petition_type=petition_type.value,
                    )
                else:
                    log.debug(
                        "Auto-escalation not triggered",
                        petition_id=str(petition_id),
                        triggered=escalation_triggered,
                    )
            except Exception as e:
                # Per Story 5.6 Error Handling: If escalation execution fails AFTER
                # co-sign persists, log error but don't fail request.
                # Co-sign is successful even if escalation fails (can be retried).
                log.error(
                    "Auto-escalation execution failed, co-sign still successful",
                    petition_id=str(petition_id),
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Step 12: Create event for witnessing (CT-12)
        # TODO(CT-12): Emit event via transactional outbox pattern when event
        # infrastructure is complete. Currently event is created for logging/audit
        # but emission is deferred until event bus integration (Epic 9).
        _co_sign_event = CoSignRecordedEvent(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash.hex(),
            co_signer_count=new_count,
            identity_verified=identity_verified,
        )
        log.debug(
            "co_sign_event_created",
            event_type="CoSignRecordedEvent",
            cosign_id=str(cosign_id),
            content_hash=content_hash.hex()[:16] + "...",
        )

        log.info(
            "Co-sign submission completed",
            cosign_id=str(cosign_id),
            co_signer_count=new_count,
            identity_verified=identity_verified,
            rate_limit_remaining=rate_limit_remaining,
            threshold_reached=threshold_reached,
            escalation_triggered=escalation_triggered,
            petition_type=petition_type.value,
        )

        # Return result with all info (rate limit + threshold + escalation)
        return CoSignSubmissionResult(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash.hex(),
            co_signer_count=new_count,
            identity_verified=identity_verified,
            rate_limit_remaining=rate_limit_remaining,
            rate_limit_reset_at=rate_limit_reset_at,
            threshold_reached=threshold_reached,
            threshold_value=threshold_value,
            petition_type=petition_type.value,
            escalation_triggered=escalation_triggered,
            escalation_id=escalation_id,
        )
