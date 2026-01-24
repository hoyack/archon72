"""Legitimacy API models (Story consent-gov-5-3).

Pydantic models for legitimacy restoration API requests and responses.

Constitutional Context:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
- AC7: Acknowledgment must include reason and evidence
"""

from datetime import datetime

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
    last_transition_type: str | None = Field(
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
    detail: str | None = Field(
        default=None,
        description="Additional error details",
    )


# ============================================================================
# Dashboard API Models (Story 8.4, FR-8.4)
# ============================================================================


class PetitionStateCountsResponse(BaseModel):
    """Petition counts by state (FR-8.4).

    Attributes:
        received: Count of petitions in RECEIVED state.
        deliberating: Count of petitions in DELIBERATING state.
        acknowledged: Count of petitions in ACKNOWLEDGED state.
        referred: Count of petitions in REFERRED state.
        escalated: Count of petitions in ESCALATED state.
        deferred: Count of petitions in DEFERRED state.
        no_response: Count of petitions in NO_RESPONSE state.
        total: Total petition count across all states.
    """

    received: int = Field(..., description="Count in RECEIVED state")
    deliberating: int = Field(..., description="Count in DELIBERATING state")
    acknowledged: int = Field(..., description="Count in ACKNOWLEDGED state")
    referred: int = Field(..., description="Count in REFERRED state")
    escalated: int = Field(..., description="Count in ESCALATED state")
    deferred: int = Field(..., description="Count in DEFERRED state")
    no_response: int = Field(..., description="Count in NO_RESPONSE state")
    total: int = Field(..., description="Total count across all states")


class DeliberationMetricsResponse(BaseModel):
    """Deliberation performance metrics (FR-8.4).

    Attributes:
        total_deliberations: Total deliberations completed this cycle.
        consensus_rate: Percentage reaching consensus (0.0-1.0).
        timeout_rate: Percentage timing out (0.0-1.0).
        deadlock_rate: Percentage deadlocking (0.0-1.0).
    """

    total_deliberations: int = Field(..., description="Total deliberations this cycle")
    consensus_rate: float = Field(..., description="Consensus rate (0.0-1.0)")
    timeout_rate: float = Field(..., description="Timeout rate (0.0-1.0)")
    deadlock_rate: float = Field(..., description="Deadlock rate (0.0-1.0)")


class ArchonAcknowledgmentRateResponse(BaseModel):
    """Per-archon acknowledgment metrics (FR-8.4).

    Attributes:
        archon_id: Archon identifier.
        archon_name: Archon display name.
        acknowledgment_count: Number of acknowledgments this cycle.
        rate: Acknowledgments per day.
    """

    archon_id: str = Field(..., description="Archon identifier")
    archon_name: str = Field(..., description="Archon display name")
    acknowledgment_count: int = Field(..., description="Acknowledgments this cycle")
    rate: float = Field(..., description="Acknowledgments per day")


class LegitimacyTrendPointResponse(BaseModel):
    """Historical legitimacy trend data point (FR-8.4).

    Attributes:
        cycle_id: Governance cycle identifier.
        legitimacy_score: Legitimacy score for this cycle (0.0-1.0).
        computed_at: When this metric was computed.
    """

    cycle_id: str = Field(..., description="Cycle identifier (e.g., 2026-W04)")
    legitimacy_score: float = Field(..., description="Score (0.0-1.0)")
    computed_at: datetime = Field(..., description="Computation timestamp")


class LegitimacyDashboardResponse(BaseModel):
    """Complete legitimacy dashboard data (Story 8.4, FR-8.4).

    High Archon dashboard aggregating petition system health metrics.

    Attributes:
        current_cycle_score: Current cycle legitimacy score (0.0-1.0).
        current_cycle_id: Current governance cycle identifier.
        health_status: Overall health (HEALTHY, WARNING, CRITICAL, NO_DATA).
        historical_trend: Last 10 cycles' legitimacy scores.
        petitions_by_state: Count of petitions in each state.
        orphan_petition_count: Count of orphan petitions.
        average_time_to_fate: Mean seconds from RECEIVED to terminal.
        median_time_to_fate: Median seconds from RECEIVED to terminal.
        deliberation_metrics: Deliberation performance metrics.
        archon_acknowledgment_rates: Per-archon acknowledgment rates.
        requires_attention: Whether dashboard indicates issues.
        data_refreshed_at: When this data was computed.
    """

    current_cycle_score: float | None = Field(
        ..., description="Current legitimacy score (0.0-1.0)"
    )
    current_cycle_id: str = Field(..., description="Current cycle ID")
    health_status: str = Field(
        ..., description="Health status (HEALTHY, WARNING, CRITICAL, NO_DATA)"
    )
    historical_trend: list[LegitimacyTrendPointResponse] = Field(
        ..., description="Last 10 cycles"
    )
    petitions_by_state: PetitionStateCountsResponse = Field(
        ..., description="Petition state distribution"
    )
    orphan_petition_count: int = Field(..., description="Orphan petition count")
    average_time_to_fate: float | None = Field(
        ..., description="Mean seconds to terminal state"
    )
    median_time_to_fate: float | None = Field(
        ..., description="Median seconds to terminal state"
    )
    deliberation_metrics: DeliberationMetricsResponse = Field(
        ..., description="Deliberation performance"
    )
    archon_acknowledgment_rates: list[ArchonAcknowledgmentRateResponse] = Field(
        ..., description="Per-archon rates"
    )
    requires_attention: bool = Field(
        ..., description="Whether issues require attention"
    )
    data_refreshed_at: datetime = Field(..., description="Data refresh timestamp")
