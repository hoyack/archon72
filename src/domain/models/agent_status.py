"""Agent status enum for domain models.

This enum defines the status of an agent in the orchestration pool.
It lives in the domain layer because domain models (like Heartbeat)
need to reference it without depending on application layer.

Architecture Note:
- Domain layer MUST NOT import from application or infrastructure
- This enum is re-exported by application ports for backward compatibility
"""

from enum import Enum


class AgentStatus(Enum):
    """Status of an agent in the orchestration pool.

    Values:
        IDLE: Agent is available for invocation.
        BUSY: Agent is currently processing a deliberation.
        FAILED: Agent encountered an error during execution.
        UNKNOWN: Agent status cannot be determined.
    """

    IDLE = "idle"
    BUSY = "busy"
    FAILED = "failed"
    UNKNOWN = "unknown"
