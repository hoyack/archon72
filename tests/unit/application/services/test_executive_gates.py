from __future__ import annotations

from src.application.services.executive_planning_service import (
    ExecutivePlanningService,
    now_iso,
)
from src.domain.models.executive_planning import (
    CapacityClaim,
    PortfolioContribution,
    PortfolioIdentity,
    RatifiedIntentPacket,
)


def _mk_packet() -> RatifiedIntentPacket:
    return RatifiedIntentPacket(
        packet_id="rip_test",
        created_at=now_iso(),
        motion_id="M-001",
        ratified_motion={"title": "Test motion", "ratified_text": "Do a thing."},
        ratification_record={"passed": True},
        review_artifacts={"dissent": []},
        provenance={"source_artifacts": []},
    )


def test_completeness_fails_when_missing_response() -> None:
    svc = ExecutivePlanningService()
    packet = _mk_packet()

    affected = [
        "portfolio_technical_solutions",
        "portfolio_resource_discovery",
    ]
    owner = "portfolio_technical_solutions"
    assignment = svc.run_assignment_session(
        packet=packet,
        affected_portfolio_ids=affected,
        plan_owner_portfolio_id=owner,
        response_deadline_iso="2099-01-01T00:00:00Z",
    )
    cycle_id = assignment["cycle_id"]

    owner_identity = PortfolioIdentity(**assignment["plan_owner"])
    contributions = [
        PortfolioContribution(
            cycle_id=cycle_id,
            motion_id=packet.motion_id,
            portfolio=owner_identity,
            tasks=[{"id": "t1"}],
            capacity_claim=CapacityClaim(
                claim_type="COARSE_ESTIMATE",
                units=5,
                unit_label="points",
            ),
            blockers=[],
        )
    ]

    result = svc.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=[],
        draft_plan=None,
    )
    assert result.gates.completeness.value == "FAIL"


def test_visibility_fails_without_capacity_claims() -> None:
    svc = ExecutivePlanningService()
    packet = _mk_packet()

    affected = ["portfolio_technical_solutions"]
    owner = "portfolio_technical_solutions"
    assignment = svc.run_assignment_session(
        packet=packet,
        affected_portfolio_ids=affected,
        plan_owner_portfolio_id=owner,
        response_deadline_iso="2099-01-01T00:00:00Z",
    )
    cycle_id = assignment["cycle_id"]

    owner_identity = PortfolioIdentity(**assignment["plan_owner"])
    contributions = [
        PortfolioContribution(
            cycle_id=cycle_id,
            motion_id=packet.motion_id,
            portfolio=owner_identity,
            tasks=[{"id": "t1"}],
            capacity_claim=None,  # type: ignore[arg-type]
            blockers=[],
        )
    ]

    result = svc.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=[],
        draft_plan=None,
    )
    assert result.gates.visibility.value == "FAIL"

