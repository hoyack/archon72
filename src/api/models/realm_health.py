"""API models for realm health endpoints (Story 8.7).

This module defines the Pydantic models for realm health API responses.

Developer Golden Rules:
1. PYDANTIC - Use Pydantic BaseModel for request/response schemas
2. OPTIONAL - Use Optional for fields that may be None
3. EXAMPLES - Include example values in Field definitions
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RealmHealthSummary(BaseModel):
    """Summary of realm health for a single realm (Story 8.7).

    Provides all health metrics and derived status for a realm.
    """

    realm_id: str = Field(
        ...,
        description="Canonical realm identifier",
        example="realm_privacy_discretion_services",
    )
    realm_display_name: str = Field(
        ...,
        description="Human-readable realm name",
        example="Privacy & Discretion Services",
    )
    cycle_id: str = Field(
        ...,
        description="Governance cycle identifier",
        example="2026-W04",
    )
    petitions_received: int = Field(
        ...,
        description="Petitions received this cycle",
        ge=0,
        example=42,
    )
    petitions_fated: int = Field(
        ...,
        description="Petitions completing Three Fates",
        ge=0,
        example=38,
    )
    referrals_pending: int = Field(
        ...,
        description="Current pending Knight referrals",
        ge=0,
        example=3,
    )
    referrals_expired: int = Field(
        ...,
        description="Referrals that expired without recommendation",
        ge=0,
        example=1,
    )
    escalations_pending: int = Field(
        ...,
        description="Petitions awaiting King decision",
        ge=0,
        example=2,
    )
    adoption_rate: Optional[float] = Field(
        None,
        description="Adoption ratio (adoptions/escalations), None if no escalations",
        ge=0,
        le=1,
        example=0.35,
    )
    average_referral_duration_seconds: Optional[int] = Field(
        None,
        description="Mean referral processing time in seconds",
        ge=0,
        example=86400,
    )
    health_status: str = Field(
        ...,
        description="Derived health status: HEALTHY, ATTENTION, DEGRADED, or CRITICAL",
        example="HEALTHY",
    )
    has_activity: bool = Field(
        ...,
        description="Whether realm has any petition activity this cycle",
        example=True,
    )
    computed_at: datetime = Field(
        ...,
        description="When health was computed (UTC)",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "realm_id": "realm_privacy_discretion_services",
                "realm_display_name": "Privacy & Discretion Services",
                "cycle_id": "2026-W04",
                "petitions_received": 42,
                "petitions_fated": 38,
                "referrals_pending": 3,
                "referrals_expired": 1,
                "escalations_pending": 2,
                "adoption_rate": 0.35,
                "average_referral_duration_seconds": 86400,
                "health_status": "HEALTHY",
                "has_activity": True,
                "computed_at": "2026-01-22T14:30:00Z",
            }
        }


class RealmHealthDeltaSummary(BaseModel):
    """Change in realm health between cycles (Story 8.7).

    Shows trend data for comparison with previous cycle.
    """

    realm_id: str = Field(
        ...,
        description="Realm identifier",
    )
    petitions_received_delta: int = Field(
        ...,
        description="Change in petitions received",
        example=5,
    )
    petitions_fated_delta: int = Field(
        ...,
        description="Change in petitions fated",
        example=3,
    )
    referrals_pending_delta: int = Field(
        ...,
        description="Change in pending referrals",
        example=-2,
    )
    escalations_pending_delta: int = Field(
        ...,
        description="Change in pending escalations",
        example=0,
    )
    adoption_rate_delta: Optional[float] = Field(
        None,
        description="Change in adoption rate",
        example=-0.05,
    )
    status_changed: bool = Field(
        ...,
        description="Whether health status changed from previous cycle",
        example=False,
    )
    previous_status: str = Field(
        ...,
        description="Previous cycle health status",
        example="HEALTHY",
    )
    current_status: str = Field(
        ...,
        description="Current cycle health status",
        example="HEALTHY",
    )
    is_improving: bool = Field(
        ...,
        description="Whether health is improving",
        example=True,
    )
    is_degrading: bool = Field(
        ...,
        description="Whether health is degrading",
        example=False,
    )


class RealmHealthWithDelta(BaseModel):
    """Realm health with optional delta from previous cycle (Story 8.7)."""

    health: RealmHealthSummary = Field(
        ...,
        description="Current cycle health metrics",
    )
    delta: Optional[RealmHealthDeltaSummary] = Field(
        None,
        description="Change from previous cycle (None if no previous data)",
    )


class RealmHealthDashboardResponse(BaseModel):
    """Dashboard response for realm health (Story 8.7).

    Provides health data for all realms with summary statistics.
    """

    cycle_id: str = Field(
        ...,
        description="Current governance cycle",
        example="2026-W04",
    )
    realms: list[RealmHealthWithDelta] = Field(
        ...,
        description="Health data for all realms",
    )
    total_realms: int = Field(
        ...,
        description="Total number of realms",
        example=9,
    )
    healthy_count: int = Field(
        ...,
        description="Realms in HEALTHY status",
        ge=0,
        example=6,
    )
    attention_count: int = Field(
        ...,
        description="Realms in ATTENTION status",
        ge=0,
        example=2,
    )
    degraded_count: int = Field(
        ...,
        description="Realms in DEGRADED status",
        ge=0,
        example=1,
    )
    critical_count: int = Field(
        ...,
        description="Realms in CRITICAL status",
        ge=0,
        example=0,
    )
    total_petitions_received: int = Field(
        ...,
        description="Total petitions received across all realms",
        ge=0,
        example=378,
    )
    total_petitions_fated: int = Field(
        ...,
        description="Total petitions fated across all realms",
        ge=0,
        example=342,
    )
    total_referrals_pending: int = Field(
        ...,
        description="Total pending referrals across all realms",
        ge=0,
        example=27,
    )
    total_escalations_pending: int = Field(
        ...,
        description="Total pending escalations across all realms",
        ge=0,
        example=12,
    )
    computed_at: datetime = Field(
        ...,
        description="When the most recent computation occurred",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "cycle_id": "2026-W04",
                "realms": [],
                "total_realms": 9,
                "healthy_count": 6,
                "attention_count": 2,
                "degraded_count": 1,
                "critical_count": 0,
                "total_petitions_received": 378,
                "total_petitions_fated": 342,
                "total_referrals_pending": 27,
                "total_escalations_pending": 12,
                "computed_at": "2026-01-22T14:30:00Z",
            }
        }
