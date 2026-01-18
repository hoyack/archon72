"""Override Service - Keeper override orchestration (Story 5.1, FR23; Story 5.2, FR24; Story 5.4, FR26).

This service orchestrates Keeper override actions, ensuring that
all overrides are logged BEFORE they take effect (FR23).
Override duration is bounded and tracked for automatic expiration (FR24).
Overrides cannot suppress witnessing (FR26 - Constitution Supremacy).

Constitutional Constraints:
- FR23: Override actions MUST be logged before they take effect
- FR24: Override duration must be bounded (max 7 days)
- FR26: Overrides cannot suppress witnessing (Constitution Supremacy)
- CT-11: Silent failure destroys legitimacy -> Log failure = NO override execution
- CT-12: Witnessing creates accountability -> OverrideEvent MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before any operation (CT-11 pattern)
2. CONSTITUTION CHECK - Validate scope does not suppress witnessing (FR26)
3. LOG FIRST - Override event MUST be written BEFORE override executes
4. FAIL LOUD - Failed log = override rejection, error returned to Keeper
5. REGISTER FOR EXPIRATION - All overrides tracked for automatic expiration (FR24)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

from src.application.ports.constitution_validator import ConstitutionValidatorProtocol
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.override_executor import OverrideExecutorPort, OverrideResult
from src.application.ports.override_registry import OverrideRegistryPort
from src.domain.errors.override import OverrideLoggingFailedError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.override_event import (
    OVERRIDE_EVENT_TYPE,
    OverrideEventPayload,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()


class OverrideService:
    """Orchestrates Keeper override actions with constitutional checks.

    This service enforces the FR23 requirement: override actions must be
    logged to the event store BEFORE they take effect, FR24 requirement
    that all overrides have bounded duration with automatic expiration,
    and FR26 requirement that overrides cannot suppress witnessing.

    Flow:
    1. HALT CHECK FIRST (CT-11 pattern)
    2. CONSTITUTION CHECK (FR26 - no witness suppression)
    3. Validate override payload (including duration bounds)
    4. Write OverrideEvent to event store FIRST
    5. Register override in registry for expiration tracking
    6. Only if write succeeds, execute override action
    7. If write fails, return error WITHOUT executing override

    Attributes:
        _event_writer: Service for writing events to the store.
        _halt_checker: Interface to check system halt state.
        _override_executor: Port for executing override actions.
        _override_registry: Optional registry for expiration tracking.
        _constitution_validator: Optional validator for FR26 enforcement.
    """

    def __init__(
        self,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
        override_executor: OverrideExecutorPort,
        override_registry: OverrideRegistryPort | None = None,
        constitution_validator: ConstitutionValidatorProtocol | None = None,
    ) -> None:
        """Initialize the Override Service.

        Args:
            event_writer: Service for writing override events.
            halt_checker: Interface to check halt state.
            override_executor: Port for executing override actions.
            override_registry: Optional registry for expiration tracking (FR24).
            constitution_validator: Optional validator for constitution supremacy (FR26).
                If provided, validates override scopes do not suppress witnessing.
        """
        self._event_writer = event_writer
        self._halt_checker = halt_checker
        self._override_executor = override_executor
        self._override_registry = override_registry
        self._constitution_validator = constitution_validator

    async def initiate_override(
        self,
        override_payload: OverrideEventPayload,
    ) -> OverrideResult:
        """Initiate a Keeper override action.

        This method enforces FR23: the override event is logged BEFORE
        the override action executes. If logging fails, the override
        action does NOT execute.

        Args:
            override_payload: Validated override payload.

        Returns:
            OverrideResult indicating success or failure.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            WitnessSuppressionAttemptError: If scope attempts to suppress witnessing (FR26).
            OverrideBlockedError: If payload validation fails.
            OverrideLoggingFailedError: If event write fails.
        """
        log = logger.bind(
            operation="initiate_override",
            keeper_id=override_payload.keeper_id,
            scope=override_payload.scope,
            action_type=override_payload.action_type.value,
        )

        # =====================================================================
        # Step 1: HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "override_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Step 2: CONSTITUTION CHECK (FR26 - no witness suppression)
        # =====================================================================
        if self._constitution_validator is not None:
            # Validate scope does not attempt to suppress witnessing
            # Raises WitnessSuppressionAttemptError if scope is forbidden
            await self._constitution_validator.validate_override_scope(
                override_payload.scope
            )
            log.info(
                "constitution_check_passed",
                message="Override scope is constitutionally valid (FR26)",
            )

        # =====================================================================
        # Step 3: Validate override payload (already validated in dataclass)
        # Additional business rule validation could go here
        # =====================================================================
        log.info(
            "override_payload_validated",
            duration=override_payload.duration,
            reason=override_payload.reason,
        )

        # =====================================================================
        # Step 4: Write OverrideEvent to event store FIRST (FR23)
        # =====================================================================
        try:
            event = await self._event_writer.write_event(
                event_type=OVERRIDE_EVENT_TYPE,
                payload={
                    "keeper_id": override_payload.keeper_id,
                    "scope": override_payload.scope,
                    "duration": override_payload.duration,
                    "reason": override_payload.reason,
                    "action_type": override_payload.action_type.value,
                    "initiated_at": override_payload.initiated_at.isoformat(),
                },
                agent_id=override_payload.keeper_id,  # Keeper acts as agent
                local_timestamp=override_payload.initiated_at,
            )

            log.info(
                "override_event_logged",
                event_id=str(event.event_id),
                sequence=event.sequence,
            )

            # =====================================================================
            # Step 4.5: Register override for expiration tracking (FR24)
            # =====================================================================
            if self._override_registry is not None:
                await self._override_registry.register_active_override(
                    override_id=event.event_id,
                    keeper_id=override_payload.keeper_id,
                    scope=override_payload.scope,
                    expires_at=override_payload.expires_at,
                )
                log.info(
                    "override_registered_for_expiration",
                    event_id=str(event.event_id),
                    expires_at=override_payload.expires_at.isoformat(),
                )

        except Exception as e:
            # =====================================================================
            # FR23: Log failure = NO override execution
            # =====================================================================
            log.error(
                "override_logging_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise OverrideLoggingFailedError(
                f"FR23: Override logging failed - override NOT executed: {e}"
            ) from e

        # =====================================================================
        # Step 5: Only if write succeeds, execute override action
        # =====================================================================
        try:
            result = await self._override_executor.execute_override(
                override_payload=override_payload,
                event_id=event.event_id,
            )

            if result.success:
                log.info(
                    "override_executed_successfully",
                    event_id=str(event.event_id),
                )
            else:
                log.warning(
                    "override_execution_failed",
                    event_id=str(event.event_id),
                    error_message=result.error_message,
                )

            return result

        except Exception as e:
            # Override event is already logged, but execution failed
            log.error(
                "override_execution_error",
                event_id=str(event.event_id),
                error=str(e),
                error_type=type(e).__name__,
            )
            return OverrideResult(
                success=False,
                event_id=event.event_id,
                error_message=f"Override execution failed: {e}",
            )
