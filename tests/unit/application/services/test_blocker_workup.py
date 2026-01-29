"""Tests for E2.5 Blocker Workup functionality."""

import pytest

from src.application.services.executive_planning_service import ExecutivePlanningService
from src.domain.models.executive_planning import (
    BlockerClass,
    BlockerDisposition,
    BlockerPacket,
    BlockerSeverity,
    BlockerV2,
    BlockerWorkupResult,
    CapacityClaim,
    ConclaveQueueItem,
    PeerReviewSummary,
    PortfolioContribution,
    PortfolioIdentity,
    RatifiedIntentPacket,
    VerificationTask,
)


def _make_packet() -> RatifiedIntentPacket:
    """Create a minimal RatifiedIntentPacket for testing."""
    return RatifiedIntentPacket(
        packet_id="rip_test123",
        created_at="2026-01-27T12:00:00Z",
        motion_id="motion_test",
        ratified_motion={
            "motion_id": "motion_test",
            "title": "Test Motion",
            "ratified_text": "Implement security framework",
            "constraints": ["security", "compliance"],
        },
        ratification_record={
            "vote_id": "vote_001",
            "outcome": "ratified",
        },
        review_artifacts={},
        provenance={},
    )


def _make_portfolio(portfolio_id: str) -> PortfolioIdentity:
    """Create a PortfolioIdentity for testing."""
    return PortfolioIdentity(
        portfolio_id=portfolio_id,
        president_id=f"president_{portfolio_id}",
        president_name=f"President of {portfolio_id}",
    )


def _make_blocker_v2(
    blocker_id: str,
    blocker_class: BlockerClass,
    disposition: BlockerDisposition,
    owner_portfolio_id: str,
) -> BlockerV2:
    """Create a BlockerV2 for testing."""
    verification_tasks = []
    mitigation_notes = None

    if disposition == BlockerDisposition.DEFER_DOWNSTREAM:
        verification_tasks = [
            VerificationTask(
                task_id=f"task_{blocker_id}",
                description="Verify blocker resolution",
                success_signal="Resolution confirmed",
            )
        ]
    elif disposition == BlockerDisposition.MITIGATE_IN_EXECUTIVE:
        mitigation_notes = "Mitigation plan documented"

    return BlockerV2(
        id=blocker_id,
        blocker_class=blocker_class,
        severity=BlockerSeverity.MEDIUM,
        description=f"Test blocker {blocker_id}",
        owner_portfolio_id=owner_portfolio_id,
        disposition=disposition,
        ttl="P7D",
        escalation_conditions=["TTL exceeded"],
        verification_tasks=verification_tasks,
        mitigation_notes=mitigation_notes,
    )


def _make_contribution_with_blockers(
    portfolio_id: str,
    blockers: list[BlockerV2],
) -> PortfolioContribution:
    """Create a PortfolioContribution with blockers."""
    return PortfolioContribution(
        cycle_id="exec_test123",
        motion_id="motion_test",
        portfolio=_make_portfolio(portfolio_id),
        tasks=[{"task_id": "task_001", "title": "Test task"}],
        capacity_claim=CapacityClaim(
            claim_type="COARSE_ESTIMATE",
            units=5.0,
            unit_label="story_points",
        ),
        blockers=blockers,
    )


class TestBlockerPacket:
    """Test BlockerPacket creation and serialization."""

    def test_from_contributions_with_v2_blockers(self):
        """BlockerPacket should extract v2 blockers from contributions."""
        blocker1 = _make_blocker_v2(
            "blocker_001",
            BlockerClass.EXECUTION_UNCERTAINTY,
            BlockerDisposition.DEFER_DOWNSTREAM,
            "portfolio_tech",
        )
        blocker2 = _make_blocker_v2(
            "blocker_002",
            BlockerClass.INTENT_AMBIGUITY,
            BlockerDisposition.ESCALATE_NOW,
            "portfolio_governance",
        )

        contributions = [
            _make_contribution_with_blockers("portfolio_tech", [blocker1]),
            _make_contribution_with_blockers("portfolio_governance", [blocker2]),
        ]

        packet = BlockerPacket.from_contributions(
            cycle_id="exec_test123",
            motion_id="motion_test",
            contributions=contributions,
            created_at="2026-01-27T12:00:00Z",
        )

        assert len(packet.blockers) == 2
        assert "portfolio_tech" in packet.source_portfolios
        assert "portfolio_governance" in packet.source_portfolios

    def test_from_contributions_empty_blockers(self):
        """BlockerPacket should handle contributions with no blockers."""
        contributions = [
            _make_contribution_with_blockers("portfolio_tech", []),
        ]

        packet = BlockerPacket.from_contributions(
            cycle_id="exec_test123",
            motion_id="motion_test",
            contributions=contributions,
            created_at="2026-01-27T12:00:00Z",
        )

        assert len(packet.blockers) == 0
        assert len(packet.source_portfolios) == 0

    def test_to_dict_includes_schema_version(self):
        """BlockerPacket.to_dict should include schema_version."""
        blocker = _make_blocker_v2(
            "blocker_001",
            BlockerClass.EXECUTION_UNCERTAINTY,
            BlockerDisposition.DEFER_DOWNSTREAM,
            "portfolio_tech",
        )

        packet = BlockerPacket(
            packet_id="bp_test123",
            cycle_id="exec_test123",
            motion_id="motion_test",
            blockers=[blocker],
            source_portfolios=["portfolio_tech"],
            created_at="2026-01-27T12:00:00Z",
        )

        data = packet.to_dict()
        assert data["schema_version"] == "2.0"
        assert len(data["blockers"]) == 1


class TestPeerReviewSummary:
    """Test PeerReviewSummary serialization and deserialization."""

    def test_to_dict_includes_all_fields(self):
        """PeerReviewSummary.to_dict should include all fields."""
        summary = PeerReviewSummary(
            cycle_id="exec_test123",
            motion_id="motion_test",
            plan_owner_portfolio_id="portfolio_tech",
            duplicates_detected=[["blocker_001", "blocker_002"]],
            conflicts_detected=[
                {
                    "blocker_ids": ["blocker_003", "blocker_004"],
                    "conflict_type": "incompatible",
                }
            ],
            coverage_gaps=["No compliance monitoring claimed"],
            blocker_disposition_rationale={
                "blocker_001": "Deferred for discovery",
                "blocker_005": "Escalated for ambiguity",
            },
            created_at="2026-01-27T12:30:00Z",
        )

        data = summary.to_dict()

        assert data["schema_version"] == "2.0"
        assert data["cycle_id"] == "exec_test123"
        assert len(data["duplicates_detected"]) == 1
        assert len(data["conflicts_detected"]) == 1
        assert len(data["coverage_gaps"]) == 1
        assert len(data["blocker_disposition_rationale"]) == 2

    def test_from_dict_round_trip(self):
        """PeerReviewSummary should round-trip through to_dict/from_dict."""
        original = PeerReviewSummary(
            cycle_id="exec_test123",
            motion_id="motion_test",
            plan_owner_portfolio_id="portfolio_tech",
            duplicates_detected=[["b1", "b2"]],
            conflicts_detected=[],
            coverage_gaps=["Gap 1"],
            blocker_disposition_rationale={"b1": "Rationale 1"},
            created_at="2026-01-27T12:30:00Z",
        )

        data = original.to_dict()
        restored = PeerReviewSummary.from_dict(data)

        assert restored.cycle_id == original.cycle_id
        assert restored.motion_id == original.motion_id
        assert restored.plan_owner_portfolio_id == original.plan_owner_portfolio_id
        assert restored.duplicates_detected == original.duplicates_detected
        assert restored.coverage_gaps == original.coverage_gaps


class TestBlockerWorkupResult:
    """Test BlockerWorkupResult serialization."""

    def test_to_dict_includes_all_artifacts(self):
        """BlockerWorkupResult.to_dict should include all artifacts."""
        blocker = _make_blocker_v2(
            "blocker_001",
            BlockerClass.INTENT_AMBIGUITY,
            BlockerDisposition.ESCALATE_NOW,
            "portfolio_governance",
        )

        summary = PeerReviewSummary(
            cycle_id="exec_test123",
            motion_id="motion_test",
            plan_owner_portfolio_id="portfolio_tech",
            duplicates_detected=[],
            conflicts_detected=[],
            coverage_gaps=[],
            blocker_disposition_rationale={"blocker_001": "Escalated"},
            created_at="2026-01-27T12:30:00Z",
        )

        queue_item = ConclaveQueueItem(
            queue_item_id="cqi_blocker_001",
            cycle_id="exec_test123",
            motion_id="motion_test",
            blocker_id="blocker_001",
            blocker_class=BlockerClass.INTENT_AMBIGUITY,
            questions=["What is the scope?"],
            options=["Option A", "Option B"],
            source_citations=["Section 1"],
            created_at="2026-01-27T12:30:00Z",
        )

        result = BlockerWorkupResult(
            cycle_id="exec_test123",
            motion_id="motion_test",
            peer_review_summary=summary,
            final_blockers=[blocker],
            conclave_queue_items=[queue_item],
            discovery_task_stubs=[],
            workup_duration_ms=150,
        )

        data = result.to_dict()

        assert data["cycle_id"] == "exec_test123"
        assert len(data["final_blockers"]) == 1
        assert len(data["conclave_queue_items"]) == 1
        assert data["workup_duration_ms"] == 150


class TestBasicBlockerWorkup:
    """Test basic (non-LLM) blocker workup in ExecutivePlanningService."""

    @pytest.fixture
    def service(self):
        """Create a service with no LLM adapters."""
        return ExecutivePlanningService(
            event_sink=lambda t, p: None,  # Absorb events
            # Uses default archons path
        )

    @pytest.fixture
    def packet(self):
        return _make_packet()

    @pytest.fixture
    def assignment_record(self):
        return {
            "cycle_id": "exec_test123",
            "motion_id": "motion_test",
            "plan_owner": {
                "portfolio_id": "portfolio_tech",
                "president_id": "president_tech",
                "president_name": "Tech President",
            },
            "affected_portfolios": [
                {
                    "portfolio_id": "portfolio_tech",
                    "president_id": "president_tech",
                    "president_name": "Tech President",
                },
                {
                    "portfolio_id": "portfolio_governance",
                    "president_id": "president_governance",
                    "president_name": "Governance President",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_basic_workup_with_escalation_blocker(
        self, service, packet, assignment_record
    ):
        """Basic workup should generate ConclaveQueueItem for ESCALATE_NOW blockers."""
        blocker = _make_blocker_v2(
            "blocker_001",
            BlockerClass.INTENT_AMBIGUITY,
            BlockerDisposition.ESCALATE_NOW,
            "portfolio_governance",
        )

        contributions = [
            _make_contribution_with_blockers("portfolio_governance", [blocker]),
        ]

        result = await service.run_blocker_workup(
            packet, assignment_record, contributions
        )

        assert len(result.conclave_queue_items) == 1
        assert result.conclave_queue_items[0].blocker_id == "blocker_001"
        assert (
            "Escalated"
            in result.peer_review_summary.blocker_disposition_rationale.get(
                "blocker_001", ""
            )
        )

    @pytest.mark.asyncio
    async def test_basic_workup_with_deferred_blocker(
        self, service, packet, assignment_record
    ):
        """Basic workup should generate DiscoveryTaskStub for DEFER_DOWNSTREAM blockers."""
        blocker = _make_blocker_v2(
            "blocker_002",
            BlockerClass.EXECUTION_UNCERTAINTY,
            BlockerDisposition.DEFER_DOWNSTREAM,
            "portfolio_tech",
        )

        contributions = [
            _make_contribution_with_blockers("portfolio_tech", [blocker]),
        ]

        result = await service.run_blocker_workup(
            packet, assignment_record, contributions
        )

        assert len(result.discovery_task_stubs) == 1
        assert result.discovery_task_stubs[0].origin_blocker_id == "blocker_002"
        assert (
            "Deferred"
            in result.peer_review_summary.blocker_disposition_rationale.get(
                "blocker_002", ""
            )
        )

    @pytest.mark.asyncio
    async def test_basic_workup_with_mitigated_blocker(
        self, service, packet, assignment_record
    ):
        """Basic workup should record rationale for MITIGATE_IN_EXECUTIVE blockers."""
        blocker = _make_blocker_v2(
            "blocker_003",
            BlockerClass.CAPACITY_CONFLICT,
            BlockerDisposition.MITIGATE_IN_EXECUTIVE,
            "portfolio_tech",
        )

        contributions = [
            _make_contribution_with_blockers("portfolio_tech", [blocker]),
        ]

        result = await service.run_blocker_workup(
            packet, assignment_record, contributions
        )

        # Mitigated blockers don't emit artifacts
        assert len(result.conclave_queue_items) == 0
        assert len(result.discovery_task_stubs) == 0
        assert (
            "Mitigated"
            in result.peer_review_summary.blocker_disposition_rationale.get(
                "blocker_003", ""
            )
        )

    @pytest.mark.asyncio
    async def test_basic_workup_no_blockers(self, service, packet, assignment_record):
        """Basic workup should handle contributions with no blockers."""
        contributions = [
            _make_contribution_with_blockers("portfolio_tech", []),
        ]

        result = await service.run_blocker_workup(
            packet, assignment_record, contributions
        )

        assert len(result.final_blockers) == 0
        assert len(result.conclave_queue_items) == 0
        assert len(result.discovery_task_stubs) == 0
        assert result.peer_review_summary.blocker_disposition_rationale == {}

    @pytest.mark.asyncio
    async def test_basic_workup_multiple_blockers(
        self, service, packet, assignment_record
    ):
        """Basic workup should handle multiple blockers from multiple portfolios."""
        blocker1 = _make_blocker_v2(
            "blocker_001",
            BlockerClass.INTENT_AMBIGUITY,
            BlockerDisposition.ESCALATE_NOW,
            "portfolio_governance",
        )
        blocker2 = _make_blocker_v2(
            "blocker_002",
            BlockerClass.EXECUTION_UNCERTAINTY,
            BlockerDisposition.DEFER_DOWNSTREAM,
            "portfolio_tech",
        )

        contributions = [
            _make_contribution_with_blockers("portfolio_governance", [blocker1]),
            _make_contribution_with_blockers("portfolio_tech", [blocker2]),
        ]

        result = await service.run_blocker_workup(
            packet, assignment_record, contributions
        )

        assert len(result.final_blockers) == 2
        assert len(result.conclave_queue_items) == 1
        assert len(result.discovery_task_stubs) == 1
        assert len(result.peer_review_summary.blocker_disposition_rationale) == 2
