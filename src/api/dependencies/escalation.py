"""Escalation queue and decision package dependencies (Stories 6.1-6.3, FR-5.4).

FastAPI dependency injection for escalation services:
- Story 6.1: Escalation queue service
- Story 6.2: Escalation decision package service
- Story 6.3: Petition adoption service

Constitutional Constraints:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- FR-5.5: King SHALL be able to ADOPT petition (creates Motion) [P0]
- CT-13: Halt check first pattern
"""

from src.application.services.acknowledgment_execution_service import (
    AcknowledgmentExecutionService,
)
from src.application.services.escalation_decision_package_service import (
    EscalationDecisionPackageService,
)
from src.application.services.escalation_queue_service import EscalationQueueService
from src.application.services.petition_adoption_service import PetitionAdoptionService

# Singleton instances (initialized at startup)
_escalation_queue_service: EscalationQueueService | None = None
_escalation_decision_package_service: EscalationDecisionPackageService | None = None
_petition_adoption_service: PetitionAdoptionService | None = None
_acknowledgment_execution_service: AcknowledgmentExecutionService | None = None


def get_escalation_queue_service() -> EscalationQueueService:
    """Get the escalation queue service singleton (Story 6.1, FR-5.4).

    This is a FastAPI dependency that provides access to the escalation
    queue service for accessing the King's escalation queue.

    Returns:
        EscalationQueueService singleton instance.

    Raises:
        RuntimeError: If service not initialized (startup error).
    """
    if _escalation_queue_service is None:
        raise RuntimeError(
            "EscalationQueueService not initialized. "
            "Call set_escalation_queue_service() during startup."
        )
    return _escalation_queue_service


def set_escalation_queue_service(service: EscalationQueueService) -> None:
    """Set the escalation queue service singleton (Story 6.1, FR-5.4).

    Called during application startup to inject the service.
    Also used in tests to inject stub implementations.

    Args:
        service: The escalation queue service instance to use.
    """
    global _escalation_queue_service
    _escalation_queue_service = service


def get_escalation_decision_package_service() -> EscalationDecisionPackageService:
    """Get the escalation decision package service singleton (Story 6.2, FR-5.4).

    This is a FastAPI dependency that provides access to the escalation
    decision package service for fetching complete escalation context.

    Returns:
        EscalationDecisionPackageService singleton instance.

    Raises:
        RuntimeError: If service not initialized (startup error).
    """
    if _escalation_decision_package_service is None:
        raise RuntimeError(
            "EscalationDecisionPackageService not initialized. "
            "Call set_escalation_decision_package_service() during startup."
        )
    return _escalation_decision_package_service


def set_escalation_decision_package_service(
    service: EscalationDecisionPackageService,
) -> None:
    """Set the escalation decision package service singleton (Story 6.2, FR-5.4).

    Called during application startup to inject the service.
    Also used in tests to inject stub implementations.

    Args:
        service: The escalation decision package service instance to use.
    """
    global _escalation_decision_package_service
    _escalation_decision_package_service = service


def get_petition_adoption_service() -> PetitionAdoptionService:
    """Get the petition adoption service singleton (Story 6.3, FR-5.5).

    This is a FastAPI dependency that provides access to the petition
    adoption service for adopting escalated petitions.

    Returns:
        PetitionAdoptionService singleton instance.

    Raises:
        RuntimeError: If service not initialized (startup error).
    """
    if _petition_adoption_service is None:
        raise RuntimeError(
            "PetitionAdoptionService not initialized. "
            "Call set_petition_adoption_service() during startup."
        )
    return _petition_adoption_service


def set_petition_adoption_service(service: PetitionAdoptionService) -> None:
    """Set the petition adoption service singleton (Story 6.3, FR-5.5).

    Called during application startup to inject the service.
    Also used in tests to inject stub implementations.

    Args:
        service: The petition adoption service instance to use.
    """
    global _petition_adoption_service
    _petition_adoption_service = service


def get_acknowledgment_execution_service() -> AcknowledgmentExecutionService:
    """Get the acknowledgment execution service singleton (Story 6.5, FR-5.8).

    This is a FastAPI dependency that provides access to the acknowledgment
    execution service for King acknowledgments.

    Returns:
        AcknowledgmentExecutionService singleton instance.

    Raises:
        RuntimeError: If service not initialized (startup error).
    """
    if _acknowledgment_execution_service is None:
        raise RuntimeError(
            "AcknowledgmentExecutionService not initialized. "
            "Call set_acknowledgment_execution_service() during startup."
        )
    return _acknowledgment_execution_service


def set_acknowledgment_execution_service(
    service: AcknowledgmentExecutionService,
) -> None:
    """Set the acknowledgment execution service singleton (Story 6.5, FR-5.8).

    Called during application startup to inject the service.
    Also used in tests to inject stub implementations.

    Args:
        service: The acknowledgment execution service instance to use.
    """
    global _acknowledgment_execution_service
    _acknowledgment_execution_service = service


__all__ = [
    "get_escalation_queue_service",
    "set_escalation_queue_service",
    "get_escalation_decision_package_service",
    "set_escalation_decision_package_service",
    "get_petition_adoption_service",
    "set_petition_adoption_service",
    "get_acknowledgment_execution_service",
    "set_acknowledgment_execution_service",
]
