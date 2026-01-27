from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.application.services.executive_planning_service import (
    ExecutivePlanningService,
    now_iso,
)
from src.domain.models.executive_planning import (
    SCHEMA_VERSION,
    BlockerClass,
    BlockerDisposition,
    BlockerSeverity,
    BlockerV2,
    BlockerWorkupResult,
    CapacityClaim,
    ConclaveQueueItem,
    DiscoveryTaskStub,
    NoActionAttestation,
    NoActionReason,
    PeerReviewSummary,
    PortfolioContribution,
    PortfolioIdentity,
    RatifiedIntentPacket,
    VerificationTask,
    WorkPackage,
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


def test_all_gates_pass_with_complete_responses() -> None:
    """Test that all gates pass when all portfolios respond with capacity claims."""
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
            tasks=[{"id": "t1", "title": "Test task"}],
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
    assert result.gates.completeness.value == "PASS"
    assert result.gates.integrity.value == "PASS"
    assert result.gates.visibility.value == "PASS"


def test_attestation_satisfies_completeness() -> None:
    """Test that a no-action attestation counts toward completeness."""
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

    # Technical Solutions contributes
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

    # Resource Discovery attests no action
    resource_identity = PortfolioIdentity(
        portfolio_id="portfolio_resource_discovery",
        president_id="dfbc91a1-5494-412f-8b91-5328170860d6",
        president_name="Valac",
    )
    attestations = [
        NoActionAttestation(
            cycle_id=cycle_id,
            motion_id=packet.motion_id,
            portfolio=resource_identity,
            reason_code=NoActionReason.MOTION_DOES_NOT_REQUIRE_MY_DOMAIN,
            explanation="This motion does not require resource discovery.",
            capacity_claim=CapacityClaim(claim_type="NONE"),
        )
    ]

    result = svc.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=attestations,
        draft_plan=None,
    )
    assert result.gates.completeness.value == "PASS"


def test_inbox_loading_contributions() -> None:
    """Test loading contributions from inbox directory."""
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

    # Create temp inbox with a contribution file
    with tempfile.TemporaryDirectory() as tmpdir:
        inbox_path = Path(tmpdir)
        contribution_data = {
            "cycle_id": cycle_id,
            "motion_id": packet.motion_id,
            "portfolio_id": "portfolio_technical_solutions",
            "president_id": "65b64f9a-6758-48e0-91ca-852e7b7b1287",
            "president_name": "Marbas",
            "tasks": [{"id": "t1", "title": "Implement security controls"}],
            "capacity_claim": {
                "claim_type": "COARSE_ESTIMATE",
                "units": 8,
                "unit_label": "story_points",
            },
            "blockers": [],
        }
        with open(inbox_path / "contribution_portfolio_technical_solutions.json", "w") as f:
            json.dump(contribution_data, f)

        contributions = svc.load_contributions_from_inbox(
            inbox_path, cycle_id, packet.motion_id
        )

        assert len(contributions) == 1
        assert contributions[0].portfolio.portfolio_id == "portfolio_technical_solutions"
        assert contributions[0].capacity_claim.units == 8
        assert len(contributions[0].tasks) == 1


def test_inbox_loading_v2_work_packages() -> None:
    """v2 contributions can be loaded from inbox using work_packages."""
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

    with tempfile.TemporaryDirectory() as tmpdir:
        inbox_path = Path(tmpdir)
        contribution_data = {
            "schema_version": "2.0",
            "cycle_id": cycle_id,
            "motion_id": packet.motion_id,
            "portfolio_id": "portfolio_technical_solutions",
            "president_id": "65b64f9a-6758-48e0-91ca-852e7b7b1287",
            "president_name": "Marbas",
            "tasks": [],
            "work_packages": [
                {
                    "package_id": "wp_security_001",
                    "epic_id": "epic_security_001",
                    "scope_description": "Harden audit logging for key subsystems",
                    "portfolio_id": "portfolio_technical_solutions",
                    "dependencies": [],
                    "constraints_respected": ["Must preserve intent"],
                }
            ],
            "capacity_claim": {
                "claim_type": "COARSE_ESTIMATE",
                "units": 8,
                "unit_label": "capacity_units",
            },
            "blockers": [],
        }
        with open(
            inbox_path / "contribution_portfolio_technical_solutions.json", "w"
        ) as f:
            json.dump(contribution_data, f)

        contributions = svc.load_contributions_from_inbox(
            inbox_path, cycle_id, packet.motion_id
        )

        assert len(contributions) == 1
        assert contributions[0].schema_version == "2.0"
        assert len(contributions[0].work_packages) == 1


def test_integrate_uses_blocker_workup_result() -> None:
    """Blocker workup results should flow into v2 plan artifacts."""
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
    work_package = WorkPackage(
        package_id="wp_exec_001",
        epic_id="epic_exec_001",
        scope_description="Define execution guardrails for the motion",
        portfolio_id=owner_identity.portfolio_id,
        dependencies=[],
        constraints_respected=["legibility"],
    )
    contribution = PortfolioContribution(
        cycle_id=cycle_id,
        motion_id=packet.motion_id,
        portfolio=owner_identity,
        tasks=[],
        work_packages=[work_package],
        capacity_claim=CapacityClaim(
            claim_type="COARSE_ESTIMATE",
            units=5,
            unit_label="capacity_units",
        ),
        blockers=[],
        schema_version="2.0",
    )

    blocker = BlockerV2(
        id="blocker_001",
        blocker_class=BlockerClass.EXECUTION_UNCERTAINTY,
        severity=BlockerSeverity.MEDIUM,
        description="Need verification before implementation",
        owner_portfolio_id="portfolio_technical_solutions",
        disposition=BlockerDisposition.DEFER_DOWNSTREAM,
        ttl="P7D",
        escalation_conditions=["No audit within TTL"],
        verification_tasks=[
            VerificationTask(
                task_id="verify_001",
                description="Conduct validation pass",
                success_signal="Validation report delivered",
            )
        ],
    )

    queue_item = ConclaveQueueItem(
        queue_item_id="cqi_001",
        cycle_id=cycle_id,
        motion_id=packet.motion_id,
        blocker_id=blocker.id,
        blocker_class=blocker.blocker_class,
        questions=["Should the motion be paused?"],
        options=["Resolve in Conclave"],
        source_citations=["from test"],
        created_at=now_iso(),
    )
    discovery_stub = DiscoveryTaskStub(
        task_id="stub_001",
        origin_blocker_id=blocker.id,
        question=blocker.description,
        deliverable="Validation report",
        max_effort=blocker.ttl,
        stop_conditions=["Validation report delivered"],
        ttl=blocker.ttl,
        escalation_conditions=blocker.escalation_conditions,
    )
    peer_review_summary = PeerReviewSummary(
        cycle_id=cycle_id,
        motion_id=packet.motion_id,
        plan_owner_portfolio_id="portfolio_technical_solutions",
        duplicates_detected=[],
        conflicts_detected=[],
        coverage_gaps=[],
        blocker_disposition_rationale={blocker.id: "Deferred to downstream audit"},
        created_at=now_iso(),
    )
    workup_result = BlockerWorkupResult(
        cycle_id=cycle_id,
        motion_id=packet.motion_id,
        peer_review_summary=peer_review_summary,
        final_blockers=[blocker],
        conclave_queue_items=[queue_item],
        discovery_task_stubs=[discovery_stub],
    )

    result = svc.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=[contribution],
        attestations=[],
        draft_plan=None,
        blocker_workup_result=workup_result,
    )

    assert result.schema_version == "2.0"
    assert len(result.conclave_queue_items) == 1
    assert len(result.discovery_task_stubs) == 1


def test_inbox_loading_attestations() -> None:
    """Test loading no-action attestations from inbox directory."""
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

    # Create temp inbox with an attestation file
    with tempfile.TemporaryDirectory() as tmpdir:
        inbox_path = Path(tmpdir)
        attestation_data = {
            "cycle_id": cycle_id,
            "motion_id": packet.motion_id,
            "portfolio_id": "portfolio_technical_solutions",
            "president_id": "65b64f9a-6758-48e0-91ca-852e7b7b1287",
            "president_name": "Marbas",
            "reason_code": "OUTSIDE_PORTFOLIO_SCOPE",
            "explanation": "This motion is outside my portfolio's scope.",
            "capacity_claim": {"claim_type": "NONE"},
        }
        with open(inbox_path / "attestation_portfolio_technical_solutions.json", "w") as f:
            json.dump(attestation_data, f)

        attestations = svc.load_attestations_from_inbox(
            inbox_path, cycle_id, packet.motion_id
        )

        assert len(attestations) == 1
        assert attestations[0].portfolio.portfolio_id == "portfolio_technical_solutions"
        assert attestations[0].reason_code == NoActionReason.OUTSIDE_PORTFOLIO_SCOPE


# -----------------------------------------------------------------------------
# v2 Legibility Gate Tests
# -----------------------------------------------------------------------------


def test_legibility_fails_with_invalid_v2_blocker() -> None:
    """Legibility gate fails when a v2 blocker is missing required fields."""
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

    # Create a v2 blocker with DEFER_DOWNSTREAM but no verification_tasks (invalid)
    invalid_blocker = BlockerV2(
        id="blocker_001",
        blocker_class=BlockerClass.EXECUTION_UNCERTAINTY,
        severity=BlockerSeverity.MEDIUM,
        description="Some uncertainty",
        owner_portfolio_id="portfolio_technical_solutions",
        disposition=BlockerDisposition.DEFER_DOWNSTREAM,
        ttl="P7D",
        escalation_conditions=["Some condition"],
        verification_tasks=[],  # Invalid: DEFER_DOWNSTREAM requires verification_tasks
    )

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
            blockers=[invalid_blocker],  # type: ignore[list-item]
        )
    ]

    result = svc.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=[],
        draft_plan=None,
    )

    assert result.gates.integrity.value == "FAIL"
    assert any("DEFER_DOWNSTREAM requires" in f for f in result.gates.failures)


def test_legibility_fails_when_intent_ambiguity_not_escalated() -> None:
    """INTENT_AMBIGUITY blocker must have ESCALATE_NOW disposition."""
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

    # INTENT_AMBIGUITY with wrong disposition
    invalid_blocker = BlockerV2(
        id="blocker_ambig",
        blocker_class=BlockerClass.INTENT_AMBIGUITY,
        severity=BlockerSeverity.HIGH,
        description="Ambiguous motion scope",
        owner_portfolio_id="portfolio_technical_solutions",
        disposition=BlockerDisposition.MITIGATE_IN_EXECUTIVE,  # Wrong!
        ttl="P1D",
        escalation_conditions=["Some condition"],
        mitigation_notes="Trying to mitigate",  # Even with notes, still invalid
    )

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
            blockers=[invalid_blocker],  # type: ignore[list-item]
        )
    ]

    result = svc.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=[],
        draft_plan=None,
    )

    assert result.gates.integrity.value == "FAIL"
    assert any("INTENT_AMBIGUITY must have disposition ESCALATE_NOW" in f for f in result.gates.failures)


def test_legibility_passes_with_valid_deferred_blocker() -> None:
    """Plans may PASS with properly configured DEFER_DOWNSTREAM blockers."""
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

    # Valid DEFER_DOWNSTREAM blocker
    valid_blocker = BlockerV2(
        id="blocker_discovery",
        blocker_class=BlockerClass.EXECUTION_UNCERTAINTY,
        severity=BlockerSeverity.MEDIUM,
        description="Need to evaluate cryptographic options",
        owner_portfolio_id="portfolio_technical_solutions",
        disposition=BlockerDisposition.DEFER_DOWNSTREAM,
        ttl="P7D",
        escalation_conditions=["Audit not completed within TTL"],
        verification_tasks=[
            VerificationTask(
                task_id="discovery_001",
                description="Conduct security audit",
                success_signal="Audit report with recommendation",
            )
        ],
    )

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
            blockers=[valid_blocker],  # type: ignore[list-item]
        )
    ]

    events: list[dict] = []
    svc_with_events = ExecutivePlanningService(
        event_sink=lambda event_type, payload: events.append(
            {"type": event_type, "payload": payload}
        ),
    )

    result = svc_with_events.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=[],
        draft_plan=None,
    )

    # Plan should pass - deferred blockers don't block planning
    assert result.gates.completeness.value == "PASS"
    assert result.gates.integrity.value == "PASS"
    assert result.gates.visibility.value == "PASS"

    # Should emit deferred_downstream event
    deferred_events = [e for e in events if e["type"] == "executive.blocker.deferred_downstream"]
    assert len(deferred_events) == 1
    assert deferred_events[0]["payload"]["blocker_id"] == "blocker_discovery"


def test_legibility_passes_with_valid_escalated_blocker() -> None:
    """Plans may PASS with properly configured ESCALATE_NOW blockers."""
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

    # Valid ESCALATE_NOW blocker (for INTENT_AMBIGUITY)
    valid_blocker = BlockerV2(
        id="blocker_ambig",
        blocker_class=BlockerClass.INTENT_AMBIGUITY,
        severity=BlockerSeverity.HIGH,
        description="Motion scope is ambiguous",
        owner_portfolio_id="portfolio_technical_solutions",
        disposition=BlockerDisposition.ESCALATE_NOW,
        ttl="P1D",
        escalation_conditions=["Conclave must clarify scope"],
    )

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
            blockers=[valid_blocker],  # type: ignore[list-item]
        )
    ]

    events: list[dict] = []
    svc_with_events = ExecutivePlanningService(
        event_sink=lambda event_type, payload: events.append(
            {"type": event_type, "payload": payload}
        ),
    )

    result = svc_with_events.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=[],
        draft_plan=None,
    )

    # Plan should pass with valid escalation
    assert result.gates.integrity.value == "PASS"

    # Should emit escalated event
    escalated_events = [e for e in events if e["type"] == "executive.blocker.escalated"]
    assert len(escalated_events) == 1
    assert escalated_events[0]["payload"]["blocker_id"] == "blocker_ambig"
    assert "queue_item_id" in escalated_events[0]["payload"]


def test_legibility_passes_with_mitigated_blocker() -> None:
    """Plans may PASS with properly configured MITIGATE_IN_EXECUTIVE blockers."""
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

    # Valid MITIGATE_IN_EXECUTIVE blocker
    valid_blocker = BlockerV2(
        id="blocker_mitigated",
        blocker_class=BlockerClass.CAPACITY_CONFLICT,
        severity=BlockerSeverity.LOW,
        description="Resource contention resolved",
        owner_portfolio_id="portfolio_technical_solutions",
        disposition=BlockerDisposition.MITIGATE_IN_EXECUTIVE,
        ttl="P3D",
        escalation_conditions=["Mitigation fails"],
        mitigation_notes="Coordinated with parallel team to sequence work",
    )

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
            blockers=[valid_blocker],  # type: ignore[list-item]
        )
    ]

    events: list[dict] = []
    svc_with_events = ExecutivePlanningService(
        event_sink=lambda event_type, payload: events.append(
            {"type": event_type, "payload": payload}
        ),
    )

    result = svc_with_events.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=[],
        draft_plan=None,
    )

    # Plan should pass
    assert result.gates.integrity.value == "PASS"

    # Should emit mitigated event
    mitigated_events = [e for e in events if e["type"] == "executive.blocker.mitigated_in_executive"]
    assert len(mitigated_events) == 1
    assert mitigated_events[0]["payload"]["blocker_id"] == "blocker_mitigated"


# ------------------------------------------------------------------------------
# v2 Epic Generation and Traceability Tests
# ------------------------------------------------------------------------------


def test_epics_generated_from_work_packages() -> None:
    """v2 contributions with work packages should generate epics."""
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

    # v2 contribution with work packages (triggers epic generation)
    wp = WorkPackage(
        package_id="wp_crypto_001",
        epic_id="epic_auto",  # Will be overwritten by generated epic
        scope_description="Implement cryptographic signing for vote records",
        portfolio_id="portfolio_technical_solutions",
        constraints_respected=["security", "auditability"],
    )

    contributions = [
        PortfolioContribution(
            cycle_id=cycle_id,
            motion_id=packet.motion_id,
            portfolio=owner_identity,
            tasks=[],
            work_packages=[wp],
            capacity_claim=CapacityClaim(
                claim_type="COARSE_ESTIMATE",
                units=5,
                unit_label="packages",
            ),
            schema_version=SCHEMA_VERSION,
        )
    ]

    events: list[dict] = []
    svc_with_events = ExecutivePlanningService(
        event_sink=lambda event_type, payload: events.append(
            {"type": event_type, "payload": payload}
        ),
    )

    result = svc_with_events.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=[],
        draft_plan=None,
    )

    # v2 mode should be detected and epics generated
    assert result.schema_version == SCHEMA_VERSION
    assert len(result.epics) > 0

    # Check epic structure
    epic = result.epics[0]
    assert epic.epic_id.startswith("epic_")
    assert len(epic.success_signals) > 0
    assert len(epic.mapped_motion_clauses) > 0  # Traceability requirement

    # Should emit epics.generated event
    epic_events = [e for e in events if e["type"] == "executive.epics.generated"]
    assert len(epic_events) == 1
    assert epic_events[0]["payload"]["epic_count"] > 0

    # Gates should pass
    assert result.gates.integrity.value == "PASS"


def test_epic_traceability_validated() -> None:
    """Epics without traceability or success signals should fail legibility."""
    # This test verifies that Epic.validate() is called during integration
    # by checking that invalid epics would cause failures.
    # Since epics are auto-generated with valid fields, we test the validation
    # logic directly here.
    from src.domain.models.executive_planning import Epic

    # Epic without mapped_motion_clauses
    bad_epic = Epic(
        epic_id="epic_bad_001",
        intent="Some intent",
        success_signals=["Signal 1"],
        constraints=[],
        assumptions=[],
        discovery_required=[],
        mapped_motion_clauses=[],  # Empty - fails traceability
    )

    errors = bad_epic.validate()
    assert len(errors) > 0
    assert any("mapped_motion_clause" in e for e in errors)
    assert any("traceability" in e for e in errors)

    # Epic without success_signals
    bad_epic2 = Epic(
        epic_id="epic_bad_002",
        intent="Some intent",
        success_signals=[],  # Empty - fails verifiability
        constraints=[],
        assumptions=[],
        discovery_required=[],
        mapped_motion_clauses=["Section 1"],
    )

    errors2 = bad_epic2.validate()
    assert len(errors2) > 0
    assert any("success_signal" in e for e in errors2)
    assert any("verifiability" in e for e in errors2)


def test_v2_plan_includes_epics_in_output() -> None:
    """v2 execution plan should include epics[] in the output."""
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

    # v2 contribution
    wp = WorkPackage(
        package_id="wp_impl_001",
        epic_id="epic_auto",
        scope_description="Implement feature X",
        portfolio_id="portfolio_technical_solutions",
        constraints_respected=["security"],
    )

    contributions = [
        PortfolioContribution(
            cycle_id=cycle_id,
            motion_id=packet.motion_id,
            portfolio=owner_identity,
            tasks=[],
            work_packages=[wp],
            capacity_claim=CapacityClaim(
                claim_type="COARSE_ESTIMATE",
                units=3,
                unit_label="packages",
            ),
            schema_version=SCHEMA_VERSION,
        )
    ]

    result = svc.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=[],
        draft_plan=None,
    )

    # Check execution_plan dict includes epics
    plan = result.execution_plan
    assert plan["schema_version"] == SCHEMA_VERSION
    assert "epics" in plan
    assert len(plan["epics"]) > 0
    assert "epic_id" in plan["epics"][0]
    assert "success_signals" in plan["epics"][0]
    assert "mapped_motion_clauses" in plan["epics"][0]
