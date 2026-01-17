"""Legitimacy API models (Story consent-gov-5-3).

Pydantic models for legitimacy restoration API requests and responses.

Constitutional Context:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
- AC7: Acknowledgment must include reason and evidence
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RestorationRequest(BaseModel):
    """Request to restore legitimacy band.

    Per AC7: Acknowledgment must include reason and evidence.
    Per AC4: Only one band up at a time.

    Attributes:
        target_band: Target band to restore to (stable, strained, eroding, compromised).
        reason: Human-readable reason for restoration.
        evidence: Evidence supporting the restoration (audit ID, etc).
    """

    target_band: str = Field(
        ...,
        description="Target band to restore to (stable, strained, eroding, compromised)",
        examples=["stable"],
    )
    reason: str = Field(
        ...,
        description="Human-readable reason for restoration",
        min_length=1,
        max_length=2000,
        examples=["Security audit completed - all issues resolved"],
    )
    evidence: str = Field(
        ...,
        description="Evidence supporting the restoration (audit ID, compliance report, etc)",
        min_length=1,
        max_length=2000,
        examples=["Audit ID: AUD-2026-0117-001"],
    )

    @field_validator("target_band")
    @classmethod
    def validate_target_band(cls, v: str) -> str:
        """Validate target band is one of the allowed values."""
        allowed = ["stable", "strained", "eroding", "compromised"]
        if v.lower() not in allowed:
            raise ValueError(f"target_band must be one of: {', '.join(allowed)}")
        return v.lower()

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reason is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("reason is required and cannot be empty")
        return v.strip()

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, v: str) -> str:
        """Validate evidence is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("evidence is required and cannot be empty")
        return v.strip()


class RestorationResponse(BaseModel):
    """Response from successful restoration.

    Attributes:
        success: Whether restoration was successful.
        acknowledgment_id: Unique ID of the acknowledgment record.
        from_band: Band before restoration.
        to_band: Band after restoration.
        operator_id: ID of operator who performed restoration.
        acknowledged_at: When restoration was acknowledged.
        reason: Reason for restoration.
        evidence: Evidence supporting restoration.
    """

    success: bool = Field(
        ...,
        description="Whether restoration was successful",
    )
    acknowledgment_id: str = Field(
        ...,
        description="Unique ID of the acknowledgment record",
    )
    from_band: str = Field(
        ...,
        description="Legitimacy band before restoration",
    )
    to_band: str = Field(
        ...,
        description="Legitimacy band after restoration",
    )
    operator_id: str = Field(
        ...,
        description="ID of operator who performed restoration",
    )
    acknowledged_at: datetime = Field(
        ...,
        description="When restoration was acknowledged",
    )
    reason: str = Field(
        ...,
        description="Reason provided for restoration",
    )
    evidence: str = Field(
        ...,
        description="Evidence provided for restoration",
    )


class LegitimacyStatusResponse(BaseModel):
    """Response for legitimacy status check.

    Attributes:
        current_band: Current legitimacy band.
        entered_at: When current band was entered.
        violation_count: Total accumulated violations.
        restoration_count: Total successful restorations.
        last_transition_type: Type of last transition (automatic/acknowledged).
    """

    current_band: str = Field(
        ...,
        description="Current legitimacy band (stable, strained, eroding, compromised, failed)",
    )
    entered_at: datetime = Field(
        ...,
        description="When the current band was entered",
    )
    violation_count: int = Field(
        ...,
        description="Total accumulated violation count",
    )
    restoration_count: int = Field(
        ...,
        description="Total successful restoration count",
    )
    last_transition_type: Optional[str] = Field(
        default=None,
        description="Type of last transition (automatic or acknowledged)",
    )


class RestorationHistoryItem(BaseModel):
    """Single restoration acknowledgment in history.

    Attributes:
        acknowledgment_id: Unique ID of acknowledgment.
        operator_id: ID of operator who performed restoration.
        from_band: Band before restoration.
        to_band: Band after restoration.
        reason: Reason for restoration.
        evidence: Evidence supporting restoration.
        acknowledged_at: When restoration was acknowledged.
    """

    acknowledgment_id: str = Field(
        ...,
        description="Unique ID of the acknowledgment",
    )
    operator_id: str = Field(
        ...,
        description="ID of operator who performed restoration",
    )
    from_band: str = Field(
        ...,
        description="Legitimacy band before restoration",
    )
    to_band: str = Field(
        ...,
        description="Legitimacy band after restoration",
    )
    reason: str = Field(
        ...,
        description="Reason provided for restoration",
    )
    evidence: str = Field(
        ...,
        description="Evidence provided for restoration",
    )
    acknowledged_at: datetime = Field(
        ...,
        description="When restoration was acknowledged",
    )


class RestorationHistoryResponse(BaseModel):
    """Response for restoration history query.

    Attributes:
        total_count: Total number of restorations.
        items: List of restoration acknowledgments.
    """

    total_count: int = Field(
        ...,
        description="Total number of restoration operations",
    )
    items: list[RestorationHistoryItem] = Field(
        ...,
        description="List of restoration acknowledgments",
    )


class LegitimacyErrorResponse(BaseModel):
    """Error response for legitimacy operations.

    Attributes:
        error: Error type.
        message: Error message.
        detail: Additional error details.
    """

    error: str = Field(
        ...,
        description="Error type (unauthorized, invalid_request, terminal_state, etc.)",
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
    detail: Optional[str] = Field(
        default=None,
        description="Additional error details",
    )
