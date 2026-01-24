"""Realm health API routes (Story 8.7, HP-7).

This module implements the API endpoints for realm health monitoring.

Constitutional Constraints:
- HP-7: Read model projections for realm health
- FR-8.1: Realm health metrics tracked per governance cycle
- HIGH_ARCHON access required for dashboard endpoints

Developer Golden Rules:
1. HIGH_ARCHON - All endpoints require HIGH_ARCHON role
2. CYCLE - Default to current cycle if not specified
3. DELTA - Include previous cycle comparison when available
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.models.realm_health import (
    RealmHealthDashboardResponse,
    RealmHealthDeltaSummary,
    RealmHealthSummary,
    RealmHealthWithDelta,
)
from src.application.ports.realm_health_repository import RealmHealthRepositoryProtocol
from src.bootstrap.realm_health import (
    get_realm_health_repository as _get_realm_health_repository,
)
from src.domain.models.realm import CANONICAL_REALM_IDS, REALM_DISPLAY_NAMES
from src.domain.models.realm_health import RealmHealth, RealmHealthDelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/governance/dashboard", tags=["governance", "realm-health"])


# Dependency injection placeholder - would be wired up in main.py
async def get_realm_health_repo() -> RealmHealthRepositoryProtocol:
    """Get realm health repository (dependency injection)."""
    # This would be injected in production
    return _get_realm_health_repository()


async def get_high_archon_id() -> UUID:
    """Get authenticated HIGH_ARCHON ID (dependency injection).

    In production, this would validate JWT and extract user ID.
    Returns 403 if user doesn't have HIGH_ARCHON role.
    """
    # Placeholder - would be implemented with auth system
    # For now, return a dummy UUID
    return UUID("00000000-0000-0000-0000-000000000001")


def get_current_cycle_id() -> str:
    """Get current governance cycle ID.

    Returns cycle in YYYY-Wnn format based on current date.
    """
    now = datetime.now(timezone.utc)
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


def _to_summary(health: RealmHealth) -> RealmHealthSummary:
    """Convert domain model to API summary."""
    return RealmHealthSummary(
        realm_id=health.realm_id,
        realm_display_name=REALM_DISPLAY_NAMES.get(health.realm_id, health.realm_id),
        cycle_id=health.cycle_id,
        petitions_received=health.petitions_received,
        petitions_fated=health.petitions_fated,
        referrals_pending=health.referrals_pending,
        referrals_expired=health.referrals_expired,
        escalations_pending=health.escalations_pending,
        adoption_rate=health.adoption_rate,
        average_referral_duration_seconds=health.average_referral_duration_seconds,
        health_status=health.health_status().value,
        has_activity=health.has_activity,
        computed_at=health.computed_at,
    )


def _to_delta_summary(delta: RealmHealthDelta) -> RealmHealthDeltaSummary:
    """Convert domain delta model to API summary."""
    return RealmHealthDeltaSummary(
        realm_id=delta.realm_id,
        petitions_received_delta=delta.petitions_received_delta,
        petitions_fated_delta=delta.petitions_fated_delta,
        referrals_pending_delta=delta.referrals_pending_delta,
        escalations_pending_delta=delta.escalations_pending_delta,
        adoption_rate_delta=delta.adoption_rate_delta,
        status_changed=delta.status_changed,
        previous_status=delta.previous_status.value,
        current_status=delta.current_status.value,
        is_improving=delta.is_improving,
        is_degrading=delta.is_degrading,
    )


@router.get(
    "/realm-health",
    response_model=RealmHealthDashboardResponse,
    summary="Get realm health dashboard data",
    description="""
    Get health metrics for all realms in the specified governance cycle.

    Requires HIGH_ARCHON role for access.

    Returns health data for all 9 canonical realms including:
    - Current cycle metrics (petitions, referrals, escalations)
    - Derived health status (HEALTHY, ATTENTION, DEGRADED, CRITICAL)
    - Comparison with previous cycle (delta values)
    - Summary statistics across all realms

    Constitutional Requirements:
    - HP-7: Read model projections for realm health
    - FR-8.1: Realm health metrics tracked per governance cycle
    """,
    responses={
        200: {"description": "Realm health data for all realms"},
        403: {"description": "User does not have HIGH_ARCHON role"},
    },
)
async def get_realm_health_dashboard(
    high_archon_id: UUID = Depends(get_high_archon_id),
    cycle_id: Optional[str] = Query(
        default=None,
        description="Governance cycle ID (YYYY-Wnn). Defaults to current cycle.",
        example="2026-W04",
    ),
    repo: RealmHealthRepositoryProtocol = Depends(get_realm_health_repo),
) -> RealmHealthDashboardResponse:
    """Get realm health dashboard data.

    Args:
        high_archon_id: Authenticated HIGH_ARCHON user ID
        cycle_id: Optional cycle ID (defaults to current)
        repo: Realm health repository

    Returns:
        RealmHealthDashboardResponse with all realm health data.

    Raises:
        HTTPException: 403 if user lacks HIGH_ARCHON role
    """
    # Use current cycle if not specified
    if cycle_id is None:
        cycle_id = get_current_cycle_id()

    logger.info(
        f"Fetching realm health dashboard for cycle {cycle_id} "
        f"by HIGH_ARCHON {high_archon_id}"
    )

    # Get health for all realms in the cycle
    health_records = await repo.get_all_for_cycle(cycle_id)

    # Build response with delta comparisons
    realms_with_delta: list[RealmHealthWithDelta] = []

    # Index health records by realm_id for easy lookup
    health_by_realm: dict[str, RealmHealth] = {h.realm_id: h for h in health_records}

    # Summary counters
    healthy_count = 0
    attention_count = 0
    degraded_count = 0
    critical_count = 0
    total_petitions_received = 0
    total_petitions_fated = 0
    total_referrals_pending = 0
    total_escalations_pending = 0
    latest_computed_at: datetime | None = None

    for realm_id in CANONICAL_REALM_IDS:
        health = health_by_realm.get(realm_id)

        if health is None:
            # Create empty health for realms with no data
            health = RealmHealth.compute(
                realm_id=realm_id,
                cycle_id=cycle_id,
            )

        # Get previous cycle for delta
        previous_health = await repo.get_previous_cycle(realm_id, cycle_id)

        delta: RealmHealthDelta | None = None
        if previous_health:
            delta = RealmHealthDelta.compute(health, previous_health)

        # Build response item
        summary = _to_summary(health)
        delta_summary = _to_delta_summary(delta) if delta else None

        realms_with_delta.append(
            RealmHealthWithDelta(
                health=summary,
                delta=delta_summary,
            )
        )

        # Update counters
        status = health.health_status().value
        if status == "HEALTHY":
            healthy_count += 1
        elif status == "ATTENTION":
            attention_count += 1
        elif status == "DEGRADED":
            degraded_count += 1
        elif status == "CRITICAL":
            critical_count += 1

        total_petitions_received += health.petitions_received
        total_petitions_fated += health.petitions_fated
        total_referrals_pending += health.referrals_pending
        total_escalations_pending += health.escalations_pending

        if latest_computed_at is None or health.computed_at > latest_computed_at:
            latest_computed_at = health.computed_at

    # Default computed_at to now if no records
    if latest_computed_at is None:
        latest_computed_at = datetime.now(timezone.utc)

    return RealmHealthDashboardResponse(
        cycle_id=cycle_id,
        realms=realms_with_delta,
        total_realms=len(CANONICAL_REALM_IDS),
        healthy_count=healthy_count,
        attention_count=attention_count,
        degraded_count=degraded_count,
        critical_count=critical_count,
        total_petitions_received=total_petitions_received,
        total_petitions_fated=total_petitions_fated,
        total_referrals_pending=total_referrals_pending,
        total_escalations_pending=total_escalations_pending,
        computed_at=latest_computed_at,
    )


@router.get(
    "/realm-health/{realm_id}",
    response_model=RealmHealthWithDelta,
    summary="Get health for a specific realm",
    description="""
    Get health metrics for a specific realm in the specified governance cycle.

    Requires HIGH_ARCHON role for access.

    Constitutional Requirements:
    - HP-7: Read model projections for realm health
    """,
    responses={
        200: {"description": "Realm health data"},
        403: {"description": "User does not have HIGH_ARCHON role"},
        404: {"description": "Realm not found or no data for cycle"},
    },
)
async def get_realm_health_by_id(
    realm_id: str,
    high_archon_id: UUID = Depends(get_high_archon_id),
    cycle_id: Optional[str] = Query(
        default=None,
        description="Governance cycle ID (YYYY-Wnn). Defaults to current cycle.",
    ),
    repo: RealmHealthRepositoryProtocol = Depends(get_realm_health_repo),
) -> RealmHealthWithDelta:
    """Get health for a specific realm.

    Args:
        realm_id: Realm identifier
        high_archon_id: Authenticated HIGH_ARCHON user ID
        cycle_id: Optional cycle ID (defaults to current)
        repo: Realm health repository

    Returns:
        RealmHealthWithDelta for the realm.

    Raises:
        HTTPException: 403 if user lacks HIGH_ARCHON role
        HTTPException: 404 if realm not found
    """
    # Validate realm_id is canonical
    if realm_id not in CANONICAL_REALM_IDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown realm: {realm_id}",
        )

    # Use current cycle if not specified
    if cycle_id is None:
        cycle_id = get_current_cycle_id()

    logger.info(
        f"Fetching realm health for {realm_id} cycle {cycle_id} "
        f"by HIGH_ARCHON {high_archon_id}"
    )

    # Get health for the realm
    health = await repo.get_by_realm_cycle(realm_id, cycle_id)

    if health is None:
        # Return empty health for realm with no data
        health = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
        )

    # Get previous cycle for delta
    previous_health = await repo.get_previous_cycle(realm_id, cycle_id)

    delta: RealmHealthDelta | None = None
    if previous_health:
        delta = RealmHealthDelta.compute(health, previous_health)

    return RealmHealthWithDelta(
        health=_to_summary(health),
        delta=_to_delta_summary(delta) if delta else None,
    )
