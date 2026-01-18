"""Halt API models (Story consent-gov-4.2).

Pydantic models for halt trigger API requests and responses.

Constitutional Context:
- FR22: Human Operator can trigger system halt
- FR23: System can execute halt operation
- AC7: Halt reason and message are required
- AC8: API returns halt status
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class HaltRequest(BaseModel):
    """Request to trigger system halt.

    Per AC7: Halt reason and message are required.

    Attributes:
        reason: Reason for halt (operator, system_fault, integrity_violation,
                consensus_failure, constitutional_breach).
        message: Human-readable description of why halt is being triggered.
    """

    reason: str = Field(
        ...,
        description="Reason for halt (operator, system_fault, integrity_violation, "
        "consensus_failure, constitutional_breach)",
        examples=["operator"],
    )
    message: str = Field(
        ...,
        description="Human-readable description of the halt reason",
        min_length=1,
        max_length=1000,
        examples=["Emergency maintenance required"],
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate halt reason is one of the allowed values."""
        allowed = [
            "operator",
            "system_fault",
            "integrity_violation",
            "consensus_failure",
            "constitutional_breach",
        ]
        if v not in allowed:
            raise ValueError(f"reason must be one of: {', '.join(allowed)}")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate halt message is not empty."""
        if not v or not v.strip():
            raise ValueError("message is required and cannot be empty")
        return v.strip()


class HaltResponse(BaseModel):
    """Response from halt trigger.

    Attributes:
        success: Whether halt was successfully established.
        halted_at: Timestamp when halt was established.
        execution_ms: Time taken to execute halt in milliseconds.
        channels_reached: List of channels that propagated the halt.
        reason: The halt reason.
        message: The halt message.
    """

    success: bool = Field(
        ...,
        description="Whether halt was successfully established",
    )
    halted_at: datetime = Field(
        ...,
        description="Timestamp when halt was established",
    )
    execution_ms: float = Field(
        ...,
        description="Time to execute halt in milliseconds",
    )
    channels_reached: list[str] = Field(
        ...,
        description="Channels that propagated the halt (primary, secondary, tertiary)",
    )
    reason: str = Field(
        ...,
        description="The halt reason",
    )
    message: str = Field(
        ...,
        description="The halt message",
    )


class HaltStatusResponse(BaseModel):
    """Response for halt status check.

    Attributes:
        is_halted: Whether system is currently halted.
        halted_at: When halt was triggered (None if not halted).
        reason: Why system was halted (None if not halted).
        message: Halt message (None if not halted).
        operator_id: ID of operator who triggered halt (None if system).
    """

    is_halted: bool = Field(
        ...,
        description="Whether system is currently halted",
    )
    halted_at: datetime | None = Field(
        default=None,
        description="When halt was triggered (None if not halted)",
    )
    reason: str | None = Field(
        default=None,
        description="Why system was halted (None if not halted)",
    )
    message: str | None = Field(
        default=None,
        description="Halt message (None if not halted)",
    )
    operator_id: str | None = Field(
        default=None,
        description="ID of operator who triggered halt (None if system)",
    )


class HaltErrorResponse(BaseModel):
    """Error response for halt operations.

    Attributes:
        error: Error type.
        message: Error message.
        detail: Additional error details.
    """

    error: str = Field(
        ...,
        description="Error type (unauthorized, invalid_request, etc.)",
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
    detail: str | None = Field(
        default=None,
        description="Additional error details",
    )
