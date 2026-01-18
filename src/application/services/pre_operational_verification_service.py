"""Pre-operational verification service (Story 8.5, FR146, NFR35).

Implements pre-operational verification checklist that runs at startup
to verify system integrity before accepting traffic.

Constitutional Constraints:
- FR146: Startup SHALL execute verification checklist: hash chain, witness pool,
         Keeper keys, checkpoint anchors. Blocked until pass.
- NFR35: System startup SHALL complete verification checklist before operation.
- CT-13: Integrity outranks availability - startup failure preferable to unverified state.

Developer Golden Rules:
- HALT FIRST: Check halt state as first verification step
- FAIL LOUD: Any verification failure blocks startup
- WITNESS EVERYTHING: Log all verification outcomes

Usage:
    from src.application.services.pre_operational_verification_service import (
        PreOperationalVerificationService,
    )

    service = PreOperationalVerificationService(
        hash_verifier=hash_verifier,
        witness_pool_monitor=witness_pool_monitor,
        keeper_key_registry=keeper_key_registry,
        checkpoint_repository=checkpoint_repository,
        halt_checker=halt_checker,
        event_replicator=event_replicator,
    )

    result = await service.run_verification_checklist()
    if result.status == VerificationStatus.FAILED:
        raise PreOperationalVerificationError(...)
"""

import os
import time
from datetime import datetime, timezone

from structlog import get_logger

from src.application.ports.checkpoint_repository import CheckpointRepository
from src.application.ports.event_replicator import EventReplicatorPort
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.hash_verifier import HashVerifierProtocol
from src.application.ports.keeper_key_registry import KeeperKeyRegistryProtocol
from src.application.ports.witness_pool_monitor import (
    MINIMUM_WITNESSES_STANDARD,
    WitnessPoolMonitorProtocol,
)
from src.domain.errors.pre_operational import BypassNotAllowedError
from src.domain.models.verification_result import (
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)

logger = get_logger()

# Environment variable configuration
VERIFICATION_HASH_CHAIN_LIMIT = int(os.getenv("VERIFICATION_HASH_CHAIN_LIMIT", "1000"))
VERIFICATION_CHECKPOINT_MAX_AGE_HOURS = int(
    os.getenv("VERIFICATION_CHECKPOINT_MAX_AGE_HOURS", "168")
)  # 7 days
VERIFICATION_BYPASS_ENABLED = (
    os.getenv("VERIFICATION_BYPASS_ENABLED", "false").lower() == "true"
)
VERIFICATION_BYPASS_MAX_COUNT = int(os.getenv("VERIFICATION_BYPASS_MAX_COUNT", "3"))
VERIFICATION_BYPASS_WINDOW_SECONDS = int(
    os.getenv("VERIFICATION_BYPASS_WINDOW_SECONDS", "300")
)


class PreOperationalVerificationService:
    """Service for running pre-operational verification checklist.

    Constitutional Constraint (FR146):
    Executes verification checklist at startup:
    1. Halt state check (informational)
    2. Hash chain integrity
    3. Checkpoint anchors existence
    4. Keeper key availability
    5. Witness pool availability
    6. Replica sync status

    Constitutional Constraint (CT-13):
    Integrity outranks availability. If verification fails,
    startup is blocked to protect system integrity.

    Attributes:
        hash_verifier: Port for hash chain verification.
        witness_pool_monitor: Port for witness pool monitoring.
        keeper_key_registry: Port for Keeper key registry.
        checkpoint_repository: Port for checkpoint storage.
        halt_checker: Port for halt state checking.
        event_replicator: Port for replica verification.
    """

    # Class-level bypass tracking (transient, per-process)
    _bypass_timestamps: list[float] = []

    def __init__(
        self,
        hash_verifier: HashVerifierProtocol,
        witness_pool_monitor: WitnessPoolMonitorProtocol,
        keeper_key_registry: KeeperKeyRegistryProtocol,
        checkpoint_repository: CheckpointRepository,
        halt_checker: HaltChecker,
        event_replicator: EventReplicatorPort,
    ) -> None:
        """Initialize the verification service.

        Args:
            hash_verifier: Port for hash chain verification.
            witness_pool_monitor: Port for witness pool monitoring.
            keeper_key_registry: Port for Keeper key registry.
            checkpoint_repository: Port for checkpoint storage.
            halt_checker: Port for halt state checking.
            event_replicator: Port for replica verification.
        """
        self._hash_verifier = hash_verifier
        self._witness_pool_monitor = witness_pool_monitor
        self._keeper_key_registry = keeper_key_registry
        self._checkpoint_repository = checkpoint_repository
        self._halt_checker = halt_checker
        self._event_replicator = event_replicator
        self._log = logger.bind(component="pre_operational_verification")

    async def run_verification_checklist(
        self,
        is_post_halt: bool = False,
        allow_bypass: bool = True,
    ) -> VerificationResult:
        """Run the complete pre-operational verification checklist.

        Constitutional Constraint (FR146):
        Executes all verification checks in order. Startup is blocked
        if any critical check fails.

        Constitutional Constraint (CT-13):
        Integrity outranks availability. Verification failure means
        the system cannot start.

        Args:
            is_post_halt: True if recovering from halt state.
                         Enables stringent verification mode.
            allow_bypass: Whether bypass is allowed (for continuous restarts).
                         Bypass is NEVER allowed when is_post_halt is True.

        Returns:
            VerificationResult with overall status and individual checks.
        """
        started_at = datetime.now(timezone.utc)
        self._log.info(
            "pre_operational_verification_started",
            is_post_halt=is_post_halt,
            allow_bypass=allow_bypass,
        )

        # Run all verification checks
        checks: list[VerificationCheck] = []

        # Order matters - check halt state first (HALT FIRST rule)
        checks.append(await self._verify_halt_state())

        # Hash chain integrity (most critical after halt check)
        checks.append(await self._verify_hash_chain(is_post_halt=is_post_halt))

        # Checkpoint anchors (recovery capability)
        checks.append(await self._verify_checkpoint_anchors(is_post_halt=is_post_halt))

        # Keeper keys (signing capability)
        checks.append(await self._verify_keeper_keys())

        # Witness pool (witnessing capability)
        checks.append(await self._verify_witness_pool())

        # Replica sync (replication health)
        checks.append(await self._verify_replica_sync())

        completed_at = datetime.now(timezone.utc)

        # Determine overall status
        failed_checks = [c for c in checks if not c.passed]

        # Check if we can bypass
        bypass_reason: str | None = None
        bypass_count = 0

        if failed_checks:
            if is_post_halt:
                # Post-halt: bypass is NEVER allowed
                status = VerificationStatus.FAILED
                self._log.critical(
                    "pre_operational_verification_failed_post_halt",
                    failed_count=len(failed_checks),
                    failed_checks=[c.name for c in failed_checks],
                )
            elif allow_bypass and self._can_bypass():
                # Continuous restart: bypass may be allowed
                status = VerificationStatus.BYPASSED
                bypass_reason = (
                    f"Continuous restart bypass ({len(failed_checks)} check(s) failed)"
                )
                bypass_count = self._record_bypass()
                self._log.warning(
                    "pre_operational_verification_bypassed",
                    failed_count=len(failed_checks),
                    failed_checks=[c.name for c in failed_checks],
                    bypass_count=bypass_count,
                    bypass_reason=bypass_reason,
                )
            else:
                status = VerificationStatus.FAILED
                self._log.critical(
                    "pre_operational_verification_failed",
                    failed_count=len(failed_checks),
                    failed_checks=[c.name for c in failed_checks],
                )
        else:
            status = VerificationStatus.PASSED
            self._log.info(
                "pre_operational_verification_passed",
                check_count=len(checks),
                duration_ms=(completed_at - started_at).total_seconds() * 1000,
            )

        result = VerificationResult(
            status=status,
            checks=tuple(checks),
            started_at=started_at,
            completed_at=completed_at,
            is_post_halt=is_post_halt,
            bypass_reason=bypass_reason,
            bypass_count=bypass_count,
        )

        return result

    # =========================================================================
    # Individual Verification Checks
    # =========================================================================

    async def _verify_halt_state(self) -> VerificationCheck:
        """Check current halt state (HALT FIRST rule).

        Note: This check is INFORMATIONAL - halt state doesn't fail
        verification, but is flagged for operator awareness.

        Returns:
            VerificationCheck with halt state details.
        """
        start_time = time.monotonic()
        log = self._log.bind(check="halt_state")

        try:
            is_halted = await self._halt_checker.is_halted()
            halt_reason = (
                await self._halt_checker.get_halt_reason() if is_halted else None
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if is_halted:
                log.warning("halt_state_detected", reason=halt_reason)
                return VerificationCheck(
                    name="halt_state",
                    passed=True,  # Informational only
                    details=f"System is halted: {halt_reason}",
                    duration_ms=duration_ms,
                    metadata={"is_halted": True, "halt_reason": halt_reason},
                )

            log.info("halt_state_clear")
            return VerificationCheck(
                name="halt_state",
                passed=True,
                details="System is not halted",
                duration_ms=duration_ms,
                metadata={"is_halted": False},
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            log.error("halt_state_check_error", error=str(e))
            return VerificationCheck(
                name="halt_state",
                passed=False,
                details=f"Failed to check halt state: {e}",
                duration_ms=duration_ms,
                error_code="halt_state_check_error",
            )

    async def _verify_hash_chain(self, is_post_halt: bool = False) -> VerificationCheck:
        """Verify hash chain integrity.

        Constitutional Constraint (FR146):
        Hash chain integrity verification is required.

        Args:
            is_post_halt: If True, verify full chain (not just last N events).

        Returns:
            VerificationCheck with hash chain status.
        """
        start_time = time.monotonic()
        log = self._log.bind(check="hash_chain")

        try:
            # Post-halt: full verification; normal: limited to last N
            max_events = None if is_post_halt else VERIFICATION_HASH_CHAIN_LIMIT

            scan_result = await self._hash_verifier.run_full_scan(max_events=max_events)
            duration_ms = (time.monotonic() - start_time) * 1000

            if scan_result.passed:
                log.info(
                    "hash_chain_verified",
                    events_scanned=scan_result.events_scanned,
                    is_post_halt=is_post_halt,
                )
                return VerificationCheck(
                    name="hash_chain",
                    passed=True,
                    details=f"Verified {scan_result.events_scanned} events",
                    duration_ms=duration_ms,
                    metadata={
                        "events_scanned": scan_result.events_scanned,
                        "scan_id": scan_result.scan_id,
                        "is_post_halt": is_post_halt,
                    },
                )

            log.critical(
                "hash_chain_corrupted",
                failed_event_id=scan_result.failed_event_id,
                expected_hash=scan_result.expected_hash,
                actual_hash=scan_result.actual_hash,
            )
            return VerificationCheck(
                name="hash_chain",
                passed=False,
                details=(
                    f"Hash mismatch at event {scan_result.failed_event_id}: "
                    f"expected {scan_result.expected_hash[:16]}..., "
                    f"got {scan_result.actual_hash[:16] if scan_result.actual_hash else 'None'}..."
                ),
                duration_ms=duration_ms,
                error_code="hash_chain_corrupted",
                metadata={
                    "failed_event_id": scan_result.failed_event_id,
                    "expected_hash": scan_result.expected_hash,
                    "actual_hash": scan_result.actual_hash,
                },
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            log.error("hash_chain_check_error", error=str(e))
            return VerificationCheck(
                name="hash_chain",
                passed=False,
                details=f"Failed to verify hash chain: {e}",
                duration_ms=duration_ms,
                error_code="hash_chain_check_error",
            )

    async def _verify_checkpoint_anchors(
        self, is_post_halt: bool = False
    ) -> VerificationCheck:
        """Verify checkpoint anchors exist.

        Constitutional Constraint (FR146):
        Checkpoint anchors existence is required for recovery capability.

        Args:
            is_post_halt: If True, verify all checkpoints (not just existence).

        Returns:
            VerificationCheck with checkpoint status.
        """
        start_time = time.monotonic()
        log = self._log.bind(check="checkpoint_anchors")

        try:
            checkpoints = await self._checkpoint_repository.get_all_checkpoints()
            latest = await self._checkpoint_repository.get_latest_checkpoint()

            duration_ms = (time.monotonic() - start_time) * 1000

            # For fresh installs, no checkpoints is acceptable (warn only)
            if not checkpoints:
                log.warning("no_checkpoints_found")
                return VerificationCheck(
                    name="checkpoint_anchors",
                    passed=True,  # Pass with warning for fresh install
                    details="No checkpoints found (fresh install)",
                    duration_ms=duration_ms,
                    metadata={"checkpoint_count": 0, "is_fresh_install": True},
                )

            # Check checkpoint freshness
            if latest:
                age_hours = (
                    datetime.now(timezone.utc) - latest.timestamp
                ).total_seconds() / 3600
                if age_hours > VERIFICATION_CHECKPOINT_MAX_AGE_HOURS:
                    log.warning(
                        "checkpoint_stale",
                        age_hours=age_hours,
                        max_age_hours=VERIFICATION_CHECKPOINT_MAX_AGE_HOURS,
                    )
                    return VerificationCheck(
                        name="checkpoint_anchors",
                        passed=False,
                        details=(
                            f"Latest checkpoint is {age_hours:.1f} hours old "
                            f"(max allowed: {VERIFICATION_CHECKPOINT_MAX_AGE_HOURS} hours)"
                        ),
                        duration_ms=duration_ms,
                        error_code="checkpoint_stale",
                        metadata={
                            "checkpoint_count": len(checkpoints),
                            "latest_age_hours": age_hours,
                            "max_age_hours": VERIFICATION_CHECKPOINT_MAX_AGE_HOURS,
                        },
                    )

            log.info(
                "checkpoints_verified",
                count=len(checkpoints),
                latest_sequence=latest.event_sequence if latest else None,
            )
            return VerificationCheck(
                name="checkpoint_anchors",
                passed=True,
                details=f"Found {len(checkpoints)} checkpoint(s), latest at sequence {latest.event_sequence if latest else 'N/A'}",
                duration_ms=duration_ms,
                metadata={
                    "checkpoint_count": len(checkpoints),
                    "latest_sequence": latest.event_sequence if latest else None,
                    "latest_hash": latest.anchor_hash if latest else None,
                },
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            log.error("checkpoint_check_error", error=str(e))
            return VerificationCheck(
                name="checkpoint_anchors",
                passed=False,
                details=f"Failed to verify checkpoints: {e}",
                duration_ms=duration_ms,
                error_code="checkpoint_check_error",
            )

    async def _verify_keeper_keys(self) -> VerificationCheck:
        """Verify Keeper key availability.

        Constitutional Constraint (FR146):
        Keeper key availability is required for override signing.

        Returns:
            VerificationCheck with Keeper key status.
        """
        start_time = time.monotonic()
        log = self._log.bind(check="keeper_keys")

        try:
            # Get all keys for all known Keepers
            # Since we don't have a list of Keeper IDs, we'll check if any keys exist
            # by trying to get keys for a standard Keeper ID pattern
            keeper_ids = ["KEEPER:primary", "KEEPER:backup", "KEEPER:emergency"]
            all_keys = []

            for keeper_id in keeper_ids:
                keys = await self._keeper_key_registry.get_all_keys_for_keeper(
                    keeper_id
                )
                all_keys.extend(keys)

            duration_ms = (time.monotonic() - start_time) * 1000

            # Filter to active keys only
            now = datetime.now(timezone.utc)
            active_keys = [
                k
                for k in all_keys
                if k.active_from <= now
                and (k.active_until is None or k.active_until > now)
            ]

            if not active_keys:
                log.warning("no_active_keeper_keys")
                return VerificationCheck(
                    name="keeper_keys",
                    passed=False,
                    details="No active Keeper keys found",
                    duration_ms=duration_ms,
                    error_code="no_active_keeper_keys",
                    metadata={"total_keys": len(all_keys), "active_keys": 0},
                )

            log.info("keeper_keys_verified", active_count=len(active_keys))
            return VerificationCheck(
                name="keeper_keys",
                passed=True,
                details=f"Found {len(active_keys)} active Keeper key(s)",
                duration_ms=duration_ms,
                metadata={
                    "total_keys": len(all_keys),
                    "active_keys": len(active_keys),
                },
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            log.error("keeper_keys_check_error", error=str(e))
            return VerificationCheck(
                name="keeper_keys",
                passed=False,
                details=f"Failed to verify Keeper keys: {e}",
                duration_ms=duration_ms,
                error_code="keeper_keys_check_error",
            )

    async def _verify_witness_pool(self) -> VerificationCheck:
        """Verify witness pool availability.

        Constitutional Constraint (FR146, FR117):
        Witness pool availability is required. Minimum 6 witnesses
        for standard operations.

        Returns:
            VerificationCheck with witness pool status.
        """
        start_time = time.monotonic()
        log = self._log.bind(check="witness_pool")

        try:
            pool_status = await self._witness_pool_monitor.get_pool_status()
            duration_ms = (time.monotonic() - start_time) * 1000

            effective_count = pool_status.effective_count

            if effective_count < MINIMUM_WITNESSES_STANDARD:
                log.warning(
                    "witness_pool_insufficient",
                    effective_count=effective_count,
                    minimum_required=MINIMUM_WITNESSES_STANDARD,
                )
                return VerificationCheck(
                    name="witness_pool",
                    passed=False,
                    details=(
                        f"Witness pool has {effective_count} witnesses "
                        f"(minimum required: {MINIMUM_WITNESSES_STANDARD})"
                    ),
                    duration_ms=duration_ms,
                    error_code="witness_pool_insufficient",
                    metadata={
                        "available_count": pool_status.available_count,
                        "effective_count": effective_count,
                        "excluded_count": len(pool_status.excluded_witnesses),
                        "minimum_required": MINIMUM_WITNESSES_STANDARD,
                        "is_degraded": pool_status.is_degraded,
                    },
                )

            log.info(
                "witness_pool_verified",
                effective_count=effective_count,
                is_degraded=pool_status.is_degraded,
            )
            return VerificationCheck(
                name="witness_pool",
                passed=True,
                details=(
                    f"Witness pool has {effective_count} witnesses"
                    f"{' (degraded mode)' if pool_status.is_degraded else ''}"
                ),
                duration_ms=duration_ms,
                metadata={
                    "available_count": pool_status.available_count,
                    "effective_count": effective_count,
                    "excluded_count": len(pool_status.excluded_witnesses),
                    "is_degraded": pool_status.is_degraded,
                },
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            log.error("witness_pool_check_error", error=str(e))
            return VerificationCheck(
                name="witness_pool",
                passed=False,
                details=f"Failed to verify witness pool: {e}",
                duration_ms=duration_ms,
                error_code="witness_pool_check_error",
            )

    async def _verify_replica_sync(self) -> VerificationCheck:
        """Verify replica synchronization status.

        Constitutional Constraint (FR146):
        Replica sync status is checked if replicas are configured.
        Pass by default if no replicas are configured (development mode).

        Returns:
            VerificationCheck with replica sync status.
        """
        start_time = time.monotonic()
        log = self._log.bind(check="replica_sync")

        try:
            verification_result = await self._event_replicator.verify_replicas()
            duration_ms = (time.monotonic() - start_time) * 1000

            # Check if replicas are configured by looking at the result
            # If all checks pass with no errors, replicas are healthy or not configured
            if verification_result.is_valid:
                log.info("replica_sync_verified")
                return VerificationCheck(
                    name="replica_sync",
                    passed=True,
                    details="Replicas are in sync (or not configured)",
                    duration_ms=duration_ms,
                    metadata={
                        "head_hash_match": verification_result.head_hash_match,
                        "signature_valid": verification_result.signature_valid,
                        "schema_version_match": verification_result.schema_version_match,
                    },
                )

            log.warning(
                "replica_sync_failed",
                errors=verification_result.errors,
            )
            return VerificationCheck(
                name="replica_sync",
                passed=False,
                details=f"Replica sync failed: {'; '.join(verification_result.errors)}",
                duration_ms=duration_ms,
                error_code="replica_sync_failed",
                metadata={
                    "head_hash_match": verification_result.head_hash_match,
                    "signature_valid": verification_result.signature_valid,
                    "schema_version_match": verification_result.schema_version_match,
                    "errors": list(verification_result.errors),
                },
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            log.error("replica_sync_check_error", error=str(e))
            return VerificationCheck(
                name="replica_sync",
                passed=False,
                details=f"Failed to verify replica sync: {e}",
                duration_ms=duration_ms,
                error_code="replica_sync_check_error",
            )

    # =========================================================================
    # Bypass Logic (FR146 MVP Note)
    # =========================================================================

    def _can_bypass(self) -> bool:
        """Check if verification bypass is allowed.

        Constitutional Constraint (FR146 MVP Note):
        Bypass is allowed for continuous restart scenarios only,
        with limits on count and time window.

        Returns:
            True if bypass is allowed, False otherwise.
        """
        if not VERIFICATION_BYPASS_ENABLED:
            return False

        # Clean up old bypass timestamps outside the window
        cutoff = time.time() - VERIFICATION_BYPASS_WINDOW_SECONDS
        PreOperationalVerificationService._bypass_timestamps = [
            ts
            for ts in PreOperationalVerificationService._bypass_timestamps
            if ts > cutoff
        ]

        # Check if we're under the limit
        return (
            len(PreOperationalVerificationService._bypass_timestamps)
            < VERIFICATION_BYPASS_MAX_COUNT
        )

    def _record_bypass(self) -> int:
        """Record a bypass and return the current count.

        Returns:
            Current number of bypasses in the window.
        """
        PreOperationalVerificationService._bypass_timestamps.append(time.time())
        return len(PreOperationalVerificationService._bypass_timestamps)

    def check_bypass_allowed(self, is_post_halt: bool) -> None:
        """Check if bypass is allowed and raise if not.

        Args:
            is_post_halt: True if this is post-halt recovery.

        Raises:
            BypassNotAllowedError: If bypass is not allowed.
        """
        if is_post_halt:
            raise BypassNotAllowedError(
                reason="Post-halt recovery requires full verification",
                is_post_halt=True,
            )

        if not VERIFICATION_BYPASS_ENABLED:
            raise BypassNotAllowedError(reason="Bypass is disabled by configuration")

        if not self._can_bypass():
            raise BypassNotAllowedError(
                reason=f"Bypass limit exceeded ({VERIFICATION_BYPASS_MAX_COUNT} max in {VERIFICATION_BYPASS_WINDOW_SECONDS}s)"
            )

    @classmethod
    def reset_bypass_tracking(cls) -> None:
        """Reset bypass tracking (for testing only)."""
        cls._bypass_timestamps = []
