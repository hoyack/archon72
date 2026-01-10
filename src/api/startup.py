"""Startup configuration and metrics for Archon 72 API (Story 6.10, Story 8.1, Story 8.5, Story 8.7).

This module provides startup hooks that:
1. Configure structured logging (Story 8.7, NFR27)
2. Validate HSM security boundary (H1 fix - security audit)
3. Validate configuration floors before the application starts serving requests
4. Run pre-operational verification checklist (Story 8.5, FR146)
5. Record service startup for metrics tracking (Story 8.1)

Constitutional Constraints:
- NFR27: Structured logging with correlation IDs
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- FR146: Startup SHALL execute verification checklist - blocked until pass
- NFR35: System startup SHALL complete verification checklist before operation
- CT-13: Integrity outranks availability -> Startup failure over running below floor
- AC1: Startup MUST fail immediately if any configuration is below floor

Security Enhancements (H1 fix):
- Validate DEV_MODE consistency with ENVIRONMENT at startup
- Prevent accidental DevHSM (plaintext keys) in production

Operational (Story 8.1):
- AC2: Record service startup for uptime tracking

Usage in FastAPI:
    @app.on_event("startup")
    async def startup_event():
        configure_logging()
        validate_hsm_security_boundary()  # H1 fix - MUST be early
        await validate_configuration_floors_at_startup()
        await run_pre_operational_verification()
        record_service_startup()

Usage standalone:
    configure_logging()
    validate_hsm_security_boundary()  # H1 fix - MUST be early
    await validate_configuration_floors_at_startup()
    await run_pre_operational_verification()
    record_service_startup()
"""

import os

from structlog import get_logger

from src.application.services.configuration_floor_enforcement_service import (
    ConfigurationFloorEnforcementService,
)
from src.application.services.pre_operational_verification_service import (
    PreOperationalVerificationService,
)
from src.domain.errors.configuration_floor import StartupFloorViolationError
from src.domain.errors.pre_operational import PreOperationalVerificationError
from src.domain.models.signable import (
    DevModeEnvironmentMismatchError,
    is_dev_mode,
    validate_dev_mode_consistency,
)
from src.domain.models.verification_result import VerificationStatus
from src.infrastructure.monitoring.metrics import get_metrics_collector
from src.infrastructure.stubs.checkpoint_repository_stub import CheckpointRepositoryStub
from src.infrastructure.stubs.event_replicator_stub import EventReplicatorStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.halt_trigger_stub import HaltTriggerStub
from src.infrastructure.stubs.hash_verifier_stub import HashVerifierStub
from src.infrastructure.observability import configure_structlog
from src.infrastructure.stubs.keeper_key_registry_stub import KeeperKeyRegistryStub
from src.infrastructure.stubs.witness_pool_monitor_stub import WitnessPoolMonitorStub

# Environment variable for environment detection
ENVIRONMENT_VAR = "ENVIRONMENT"
DEFAULT_ENVIRONMENT = "development"

logger = get_logger()


def configure_logging() -> None:
    """Configure structured logging for the application (Story 8.7, AC3).

    This function configures structlog based on the ENVIRONMENT variable:
    - production: JSON output for log aggregation
    - development (default): Colored console output

    Should be called first in the startup sequence, before any logging occurs.

    Constitutional Constraint (NFR27):
    Structured logging with correlation IDs for distributed tracing.
    """
    environment = os.getenv(ENVIRONMENT_VAR, DEFAULT_ENVIRONMENT)
    configure_structlog(environment=environment)

    log = get_logger().bind(component="startup_logging")
    log.info("structured_logging_configured", environment=environment)


def validate_hsm_security_boundary() -> None:
    """Validate HSM security boundary at startup (H1 security fix).

    This function MUST be called early in startup, before any HSM operations.
    It validates that DEV_MODE and ENVIRONMENT are consistent to prevent
    accidental use of DevHSM (plaintext keys) in production.

    H1 Security Finding:
    - Single environment variable (DEV_MODE) controls whether DevHSM or
      CloudHSM is used for cryptographic operations
    - An attacker who can modify environment variables could force
      development mode in production, compromising cryptographic security

    This fix adds secondary validation:
    - DEV_MODE=true is only allowed in development/test environments
    - DEV_MODE=true in production/staging raises DevModeEnvironmentMismatchError

    Raises:
        DevModeEnvironmentMismatchError: If DEV_MODE=true in production environment.
    """
    log = logger.bind(component="hsm_security_boundary")
    log.info(
        "hsm_security_boundary_validation_started",
        dev_mode=is_dev_mode(),
        environment=os.getenv(ENVIRONMENT_VAR, DEFAULT_ENVIRONMENT),
    )

    try:
        validate_dev_mode_consistency()
        log.info(
            "hsm_security_boundary_validation_passed",
            dev_mode=is_dev_mode(),
            environment=os.getenv(ENVIRONMENT_VAR, DEFAULT_ENVIRONMENT),
        )
    except DevModeEnvironmentMismatchError:
        log.critical(
            "hsm_security_boundary_validation_failed",
            dev_mode=is_dev_mode(),
            environment=os.getenv(ENVIRONMENT_VAR, DEFAULT_ENVIRONMENT),
            message="H1: Startup blocked - DEV_MODE=true in production environment",
        )
        raise


async def validate_configuration_floors_at_startup() -> None:
    """Validate all configuration floors at startup.

    This function MUST be called before the application starts
    serving requests. If any configuration is below its floor,
    startup is blocked with StartupFloorViolationError.

    Constitutional Constraint (NFR39):
    No configuration SHALL allow thresholds below constitutional floors.

    Constitutional Constraint (CT-13):
    Integrity outranks availability. Startup failure is preferable
    to running with configuration below constitutional minimums.

    Raises:
        StartupFloorViolationError: If any configuration is below its floor.
    """
    log = logger.bind(component="startup_validation")
    log.info("configuration_floor_validation_started")

    # Create service (using stub halt trigger since we're at startup)
    # In production, the real halt trigger would be injected
    halt_trigger = HaltTriggerStub()
    service = ConfigurationFloorEnforcementService(halt_trigger=halt_trigger)

    # Validate all configurations
    result = await service.validate_startup_configuration()

    if result.is_valid:
        log.info(
            "configuration_floor_validation_passed",
            validated_count=result.validated_count,
        )
        return

    # Validation failed - log and raise
    log.critical(
        "configuration_floor_validation_failed",
        violation_count=len(result.violations),
        violations=[
            {
                "threshold": v.threshold_name,
                "attempted": v.attempted_value,
                "floor": v.floor_value,
                "fr_reference": v.fr_reference,
            }
            for v in result.violations
        ],
    )

    # Raise error for first violation (all will be logged above)
    first_violation = result.violations[0]
    raise StartupFloorViolationError(
        threshold_name=first_violation.threshold_name,
        attempted_value=first_violation.attempted_value,
        constitutional_floor=first_violation.floor_value,
        fr_reference=first_violation.fr_reference,
    )


async def run_pre_operational_verification(is_post_halt: bool = False) -> None:
    """Run pre-operational verification checklist (Story 8.5, FR146, NFR35).

    This function MUST be called before the application starts serving
    requests, after configuration floor validation. If any verification
    check fails, startup is blocked with PreOperationalVerificationError.

    Constitutional Constraint (FR146):
    Startup SHALL execute verification checklist:
    - Hash chain integrity
    - Witness pool availability
    - Keeper key availability
    - Checkpoint anchors existence
    - Halt state check (informational)
    - Replica sync status

    Constitutional Constraint (NFR35):
    System startup SHALL complete verification checklist before operation.

    Constitutional Constraint (CT-13):
    Integrity outranks availability. Startup failure is preferable
    to running with unverified system state.

    Args:
        is_post_halt: True if recovering from a previous halt state.
                     Enables stringent verification mode with no bypass allowed.

    Raises:
        PreOperationalVerificationError: If verification fails.
    """
    log = logger.bind(
        component="pre_operational_verification",
        is_post_halt=is_post_halt,
    )
    log.info("pre_operational_verification_started")

    # Create service with stub dependencies
    # In production, real implementations would be injected via dependency injection
    service = PreOperationalVerificationService(
        hash_verifier=HashVerifierStub(),
        witness_pool_monitor=WitnessPoolMonitorStub(),
        keeper_key_registry=KeeperKeyRegistryStub(),
        checkpoint_repository=CheckpointRepositoryStub(),
        halt_checker=HaltCheckerStub(),
        event_replicator=EventReplicatorStub(),
    )

    # Determine if bypass is allowed (Finding 5 security fix)
    # Bypass requires:
    # 1. Not recovering from halt (is_post_halt=False)
    # 2. Explicit ALLOW_VERIFICATION_BYPASS=true environment variable
    # 3. Not in production environment
    allow_bypass = (
        not is_post_halt
        and os.getenv("ALLOW_VERIFICATION_BYPASS", "false").lower() == "true"
        and os.getenv(ENVIRONMENT_VAR, DEFAULT_ENVIRONMENT).lower()
        not in ("production", "prod", "staging", "stage")
    )

    if allow_bypass:
        log.warning(
            "verification_bypass_enabled",
            message="ALLOW_VERIFICATION_BYPASS is enabled - NOT FOR PRODUCTION USE",
        )

    # Run the verification checklist
    result = await service.run_verification_checklist(
        is_post_halt=is_post_halt,
        allow_bypass=allow_bypass,
    )

    # Log result
    log.info(
        "pre_operational_verification_completed",
        status=result.status.value,
        check_count=result.check_count,
        failure_count=result.failure_count,
        duration_ms=result.duration_ms,
        is_post_halt=result.is_post_halt,
        bypass_reason=result.bypass_reason,
    )

    # Handle based on status
    if result.status == VerificationStatus.PASSED:
        log.info("pre_operational_verification_passed")
        return

    if result.status == VerificationStatus.BYPASSED:
        log.warning(
            "pre_operational_verification_bypassed",
            bypass_reason=result.bypass_reason,
            bypass_count=result.bypass_count,
        )
        return

    # Status is FAILED - raise error
    log.critical(
        "pre_operational_verification_failed",
        failed_checks=[
            {
                "name": c.name,
                "details": c.details,
                "error_code": c.error_code,
            }
            for c in result.failed_checks
        ],
    )

    raise PreOperationalVerificationError(
        failed_checks=result.failed_checks,
        result=result,
    )


def record_service_startup(service_name: str = "api") -> None:
    """Record service startup for metrics tracking (Story 8.1, AC2).

    Records the startup time for uptime calculation and increments
    the service starts counter.

    Args:
        service_name: Name of the service (default: "api").
    """
    log = logger.bind(component="startup_metrics", service=service_name)
    log.info("recording_service_startup")

    collector = get_metrics_collector()
    collector.record_startup(service_name)

    log.info("service_startup_recorded", service=service_name)
