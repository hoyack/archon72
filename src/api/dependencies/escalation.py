"""Escalation queue dependencies (Story 6.1, FR-5.4).

FastAPI dependency injection for escalation queue service.

Constitutional Constraints:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- CT-13: Halt check first pattern
"""

from src.application.services.escalation_queue_service import EscalationQueueService

# Singleton instance (initialized at startup)
_escalation_queue_service: EscalationQueueService | None = None


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


__all__ = [
    "get_escalation_queue_service",
    "set_escalation_queue_service",
]
