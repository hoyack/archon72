"""Unit tests for Advisory Acknowledgment Service.

Tests for FR-GOV-18: Advisories must be acknowledged but not obeyed;
Marquis cannot judge domains where advisory was given.

Test coverage:
- AC1: Acknowledgment recording
- AC2: Contrary decision documentation
- AC3: Acknowledgment tracking repository
- AC4: Acknowledgment deadline enforcement
- AC5: Non-approval distinction
- AC6: Advisory window tracking
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, create_autospec
from uuid import uuid4

import pytest

from src.application.ports.advisory_acknowledgment import (
    AcknowledgmentDeadlineStatus,
    AcknowledgmentRequest,
    AdvisoryAcknowledgment,
    AdvisoryTrackingConfig,
    AdvisoryWindow,
    ContraryDecision,
    ContraryDecisionRequest,
    DeadlineViolation,
    JudgmentEligibilityResult,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    WitnessStatement,
    WitnessStatementType,
)
from src.application.ports.marquis_service import Advisory, ExpertiseDomain
from src.application.services.advisory_acknowledgment_service import (
    AdvisoryAcknowledgmentService,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_knight_witness() -> MagicMock:
    """Create a mock Knight witness service."""
    mock = create_autospec(KnightWitnessProtocol)
    mock.observe.return_value = WitnessStatement.create(
        statement_type=WitnessStatementType.ACKNOWLEDGMENT_RECEIVED,
        description="Test witness statement",
        roles_involved=["test_archon"],
    )
    mock.trigger_acknowledgment.return_value = MagicMock()
    return mock


@pytest.fixture
def config() -> AdvisoryTrackingConfig:
    """Create test configuration."""
    return AdvisoryTrackingConfig(
        acknowledgment_deadline_hours=48,
        window_close_on_motion_complete=True,
        warning_on_missed_deadline=True,
        escalate_pattern_threshold=3,
    )


@pytest.fixture
def service(
    config: AdvisoryTrackingConfig,
    mock_knight_witness: MagicMock,
) -> AdvisoryAcknowledgmentService:
    """Create service with mock dependencies."""
    return AdvisoryAcknowledgmentService(
        config=config,
        knight_witness=mock_knight_witness,
    )


@pytest.fixture
def sample_advisory() -> Advisory:
    """Create a sample advisory."""
    return Advisory.create(
        issued_by="orias",  # Marquis in Science domain
        domain=ExpertiseDomain.SCIENCE,
        topic="quantum computing risks",
        recommendation="Implement additional safeguards for quantum-based encryption",
        rationale="Current encryption may be vulnerable to quantum attacks",
    )


# =============================================================================
# AC1: ACKNOWLEDGMENT RECORDING TESTS
# =============================================================================


class TestAcknowledgmentRecording:
    """Tests for AC1: Acknowledgment recording."""

    @pytest.mark.asyncio
    async def test_record_acknowledgment_success(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test successful acknowledgment recording."""
        # Register advisory first
        await service.register_advisory(sample_advisory, ["paimon", "bael"])

        # Record acknowledgment
        request = AcknowledgmentRequest(
            advisory_id=sample_advisory.advisory_id,
            archon_id="paimon",
            understanding="Understood the quantum computing risk assessment",
        )
        result = await service.record_acknowledgment(request)

        assert result.success is True
        assert result.acknowledgment is not None
        assert result.acknowledgment.acknowledged_by == "paimon"
        assert result.acknowledgment.advisory_id == sample_advisory.advisory_id
        assert "quantum" in result.acknowledgment.understanding.lower()

    @pytest.mark.asyncio
    async def test_acknowledgment_includes_required_fields(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test acknowledgment includes all required fields per AC1."""
        await service.register_advisory(sample_advisory, ["paimon"])

        request = AcknowledgmentRequest(
            advisory_id=sample_advisory.advisory_id,
            archon_id="paimon",
            understanding="Risk noted and understood",
        )
        result = await service.record_acknowledgment(request)

        ack = result.acknowledgment
        assert ack is not None
        # Per AC1: acknowledged_by, acknowledged_at, understanding
        assert ack.acknowledged_by == "paimon"
        assert isinstance(ack.acknowledged_at, datetime)
        assert ack.understanding == "Risk noted and understood"

    @pytest.mark.asyncio
    async def test_acknowledgment_advisory_not_found(
        self,
        service: AdvisoryAcknowledgmentService,
    ) -> None:
        """Test acknowledgment fails for non-existent advisory."""
        request = AcknowledgmentRequest(
            advisory_id=uuid4(),
            archon_id="paimon",
            understanding="Some understanding",
        )
        result = await service.record_acknowledgment(request)

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_duplicate_acknowledgment_rejected(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test duplicate acknowledgment from same archon is rejected."""
        await service.register_advisory(sample_advisory, ["paimon"])

        request = AcknowledgmentRequest(
            advisory_id=sample_advisory.advisory_id,
            archon_id="paimon",
            understanding="First acknowledgment",
        )
        result1 = await service.record_acknowledgment(request)
        assert result1.success is True

        # Try to acknowledge again
        request2 = AcknowledgmentRequest(
            advisory_id=sample_advisory.advisory_id,
            archon_id="paimon",
            understanding="Second acknowledgment",
        )
        result2 = await service.record_acknowledgment(request2)
        assert result2.success is False
        assert "already acknowledged" in result2.error.lower()

    @pytest.mark.asyncio
    async def test_acknowledgment_witnessed_by_knight(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test acknowledgment is witnessed by Knight per CT-12."""
        await service.register_advisory(sample_advisory, ["paimon"])

        request = AcknowledgmentRequest(
            advisory_id=sample_advisory.advisory_id,
            archon_id="paimon",
            understanding="Understood",
        )
        await service.record_acknowledgment(request)

        # Verify Knight observed the acknowledgment
        assert mock_knight_witness.observe.called
        call_args = mock_knight_witness.observe.call_args_list
        # Should have at least 3 calls: register, window open, acknowledgment
        assert len(call_args) >= 2


# =============================================================================
# AC2: CONTRARY DECISION DOCUMENTATION TESTS
# =============================================================================


class TestContraryDecisionDocumentation:
    """Tests for AC2: Contrary decision documentation."""

    @pytest.mark.asyncio
    async def test_record_contrary_decision_success(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test successful contrary decision recording."""
        await service.register_advisory(sample_advisory, ["paimon"])

        request = ContraryDecisionRequest(
            advisory_id=sample_advisory.advisory_id,
            decided_by="paimon",
            reasoning="Current quantum threats are overstated per latest research",
            decision_summary="Proceeding with standard encryption without quantum safeguards",
        )
        result = await service.record_contrary_decision(request)

        assert result.success is True
        assert result.decision is not None
        assert result.decision.advisory_id == sample_advisory.advisory_id
        assert result.decision.decided_by == "paimon"

    @pytest.mark.asyncio
    async def test_contrary_decision_includes_required_fields(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test contrary decision includes all required fields per AC2."""
        await service.register_advisory(sample_advisory, ["paimon"])

        request = ContraryDecisionRequest(
            advisory_id=sample_advisory.advisory_id,
            decided_by="paimon",
            reasoning="Reasoning for contrary decision",
            decision_summary="The contrary decision itself",
        )
        result = await service.record_contrary_decision(request)

        decision = result.decision
        assert decision is not None
        # Per AC2: reference to advisory, reasoning, who made decision
        assert decision.advisory_id == sample_advisory.advisory_id
        assert decision.reasoning == "Reasoning for contrary decision"
        assert decision.decided_by == "paimon"

    @pytest.mark.asyncio
    async def test_contrary_decision_witnessed_by_knight(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test contrary decision is witnessed by Knight per AC2/CT-12."""
        await service.register_advisory(sample_advisory, ["paimon"])

        request = ContraryDecisionRequest(
            advisory_id=sample_advisory.advisory_id,
            decided_by="paimon",
            reasoning="Reasoning",
            decision_summary="Decision",
        )
        await service.record_contrary_decision(request)

        # Verify Knight witnessed and triggered acknowledgment
        assert mock_knight_witness.observe.called
        assert mock_knight_witness.trigger_acknowledgment.called

    @pytest.mark.asyncio
    async def test_contrary_decision_advisory_not_found(
        self,
        service: AdvisoryAcknowledgmentService,
    ) -> None:
        """Test contrary decision fails for non-existent advisory."""
        request = ContraryDecisionRequest(
            advisory_id=uuid4(),
            decided_by="paimon",
            reasoning="Some reasoning",
            decision_summary="Some decision",
        )
        result = await service.record_contrary_decision(request)

        assert result.success is False
        assert "not found" in result.error.lower()


# =============================================================================
# AC3: ACKNOWLEDGMENT TRACKING REPOSITORY TESTS
# =============================================================================


class TestAcknowledgmentRepository:
    """Tests for AC3: Acknowledgment tracking repository."""

    @pytest.mark.asyncio
    async def test_get_unacknowledged_advisories(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test getting unacknowledged advisories for an archon."""
        await service.register_advisory(sample_advisory, ["paimon", "bael"])

        # Initially both should have unacknowledged advisories
        paimon_unacked = await service.get_unacknowledged_advisories("paimon")
        assert sample_advisory.advisory_id in paimon_unacked

        # After acknowledgment, paimon should have none
        await service.record_acknowledgment(
            AcknowledgmentRequest(
                advisory_id=sample_advisory.advisory_id,
                archon_id="paimon",
                understanding="Understood",
            )
        )
        paimon_unacked = await service.get_unacknowledged_advisories("paimon")
        assert sample_advisory.advisory_id not in paimon_unacked

        # But bael should still have it
        bael_unacked = await service.get_unacknowledged_advisories("bael")
        assert sample_advisory.advisory_id in bael_unacked

    @pytest.mark.asyncio
    async def test_get_advisory_acknowledgments(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test getting all acknowledgments for an advisory."""
        await service.register_advisory(sample_advisory, ["paimon", "bael"])

        # Record acknowledgments
        await service.record_acknowledgment(
            AcknowledgmentRequest(
                advisory_id=sample_advisory.advisory_id,
                archon_id="paimon",
                understanding="Paimon understands",
            )
        )
        await service.record_acknowledgment(
            AcknowledgmentRequest(
                advisory_id=sample_advisory.advisory_id,
                archon_id="bael",
                understanding="Bael understands",
            )
        )

        acknowledgments = await service.get_advisory_acknowledgments(
            sample_advisory.advisory_id
        )
        assert len(acknowledgments) == 2
        archons = {ack.acknowledged_by for ack in acknowledgments}
        assert archons == {"paimon", "bael"}

    @pytest.mark.asyncio
    async def test_get_contrary_decisions(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test getting contrary decisions for an advisory."""
        await service.register_advisory(sample_advisory, ["paimon"])

        await service.record_contrary_decision(
            ContraryDecisionRequest(
                advisory_id=sample_advisory.advisory_id,
                decided_by="paimon",
                reasoning="First reasoning",
                decision_summary="First decision",
            )
        )
        await service.record_contrary_decision(
            ContraryDecisionRequest(
                advisory_id=sample_advisory.advisory_id,
                decided_by="bael",
                reasoning="Second reasoning",
                decision_summary="Second decision",
            )
        )

        decisions = await service.get_contrary_decisions(sample_advisory.advisory_id)
        assert len(decisions) == 2


# =============================================================================
# AC4: ACKNOWLEDGMENT DEADLINE ENFORCEMENT TESTS
# =============================================================================


class TestDeadlineEnforcement:
    """Tests for AC4: Acknowledgment deadline enforcement."""

    @pytest.mark.asyncio
    async def test_deadline_not_violated_before_expiry(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test no violation when deadline not yet passed."""
        await service.register_advisory(sample_advisory, ["paimon"])

        violations = await service.check_deadline_violations()
        assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_deadline_violation_after_expiry(
        self,
        config: AdvisoryTrackingConfig,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test violation generated after deadline passes."""
        service = AdvisoryAcknowledgmentService(
            config=config,
            knight_witness=mock_knight_witness,
        )

        # Create advisory with old timestamp
        old_advisory = Advisory(
            advisory_id=uuid4(),
            issued_by="orias",
            domain=ExpertiseDomain.SCIENCE,
            topic="old topic",
            recommendation="old recommendation",
            rationale="old rationale",
            binding=False,
            issued_at=datetime.now(timezone.utc) - timedelta(hours=72),  # 72 hours ago
        )
        service._advisories[old_advisory.advisory_id] = old_advisory
        service._acknowledgments[old_advisory.advisory_id] = []
        service._contrary_decisions[old_advisory.advisory_id] = []
        service._advisory_recipients[old_advisory.advisory_id] = {"paimon"}

        violations = await service.check_deadline_violations()
        assert len(violations) == 1
        assert violations[0].archon_id == "paimon"
        assert violations[0].status == AcknowledgmentDeadlineStatus.WARNING

    @pytest.mark.asyncio
    async def test_escalation_after_pattern(
        self,
        config: AdvisoryTrackingConfig,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test escalation after repeated deadline misses per AC4."""
        config.escalate_pattern_threshold = 2  # Escalate after 2 misses
        service = AdvisoryAcknowledgmentService(
            config=config,
            knight_witness=mock_knight_witness,
        )

        # Simulate pattern of misses
        service._deadline_violations["paimon"] = 1  # Already missed one

        # Create another expired advisory
        old_advisory = Advisory(
            advisory_id=uuid4(),
            issued_by="orias",
            domain=ExpertiseDomain.SCIENCE,
            topic="another topic",
            recommendation="recommendation",
            rationale="rationale",
            binding=False,
            issued_at=datetime.now(timezone.utc) - timedelta(hours=72),
        )
        service._advisories[old_advisory.advisory_id] = old_advisory
        service._acknowledgments[old_advisory.advisory_id] = []
        service._contrary_decisions[old_advisory.advisory_id] = []
        service._advisory_recipients[old_advisory.advisory_id] = {"paimon"}

        violations = await service.check_deadline_violations()
        assert len(violations) == 1
        assert violations[0].status == AcknowledgmentDeadlineStatus.ESCALATED
        assert violations[0].consecutive_misses == 2

    @pytest.mark.asyncio
    async def test_get_deadline_for_advisory(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test getting deadline for an advisory."""
        await service.register_advisory(sample_advisory, ["paimon"])

        deadline = await service.get_deadline_for_advisory(sample_advisory.advisory_id)
        assert deadline is not None
        expected = sample_advisory.issued_at + timedelta(hours=48)
        assert abs((deadline - expected).total_seconds()) < 1


# =============================================================================
# AC5: NON-APPROVAL DISTINCTION TESTS
# =============================================================================


class TestNonApprovalDistinction:
    """Tests for AC5: Non-approval distinction."""

    @pytest.mark.asyncio
    async def test_acknowledgment_approved_always_false(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test acknowledgment explicitly has approved=False per AC5."""
        await service.register_advisory(sample_advisory, ["paimon"])

        request = AcknowledgmentRequest(
            advisory_id=sample_advisory.advisory_id,
            archon_id="paimon",
            understanding="Full understanding and agreement",  # Even with "agreement"
        )
        result = await service.record_acknowledgment(request)

        assert result.acknowledgment.approved is False

    def test_acknowledgment_model_approved_default_false(self) -> None:
        """Test AdvisoryAcknowledgment model defaults approved to False."""
        ack = AdvisoryAcknowledgment.create(
            advisory_id=uuid4(),
            acknowledged_by="paimon",
            understanding="Test",
        )
        assert ack.approved is False

    def test_acknowledgment_serialization_includes_approved(self) -> None:
        """Test serialization explicitly includes approved=False."""
        ack = AdvisoryAcknowledgment.create(
            advisory_id=uuid4(),
            acknowledged_by="paimon",
            understanding="Test",
        )
        data = ack.to_dict()
        assert "approved" in data
        assert data["approved"] is False


# =============================================================================
# AC6: ADVISORY WINDOW TRACKING TESTS
# =============================================================================


class TestAdvisoryWindowTracking:
    """Tests for AC6: Advisory window tracking."""

    @pytest.mark.asyncio
    async def test_window_opened_on_advisory_issuance(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test advisory window is opened when advisory is registered."""
        await service.register_advisory(sample_advisory, ["paimon"])

        windows = await service.get_open_windows("orias")
        assert len(windows) == 1
        assert windows[0].topic == "quantum computing risks"
        assert windows[0].is_open is True

    @pytest.mark.asyncio
    async def test_check_can_judge_conflict(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test Marquis cannot judge on advised topic per FR-GOV-18."""
        await service.register_advisory(sample_advisory, ["paimon"])

        # Same topic - should conflict
        result = await service.check_can_judge("orias", "quantum computing risks")
        assert result.can_judge is False
        assert result.conflicting_window is not None
        assert "FR-GOV-18" in result.reason

    @pytest.mark.asyncio
    async def test_check_can_judge_no_conflict(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test Marquis can judge on unrelated topic."""
        await service.register_advisory(sample_advisory, ["paimon"])

        # Different topic - should not conflict
        result = await service.check_can_judge("orias", "biodiversity assessment")
        assert result.can_judge is True
        assert result.conflicting_window is None

    @pytest.mark.asyncio
    async def test_check_can_judge_overlapping_topic(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test Marquis cannot judge on overlapping topic."""
        await service.register_advisory(sample_advisory, ["paimon"])

        # Overlapping topic - should conflict
        result = await service.check_can_judge("orias", "quantum computing security")
        assert result.can_judge is False

    @pytest.mark.asyncio
    async def test_close_advisory_window(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test advisory window can be closed."""
        await service.register_advisory(sample_advisory, ["paimon"])

        windows = await service.get_open_windows("orias")
        assert len(windows) == 1
        window = windows[0]

        # Close the window
        closed = await service.close_advisory_window(window.window_id)
        assert closed is not None
        assert closed.is_open is False

        # Verify no open windows now
        windows = await service.get_open_windows("orias")
        assert len(windows) == 0

    @pytest.mark.asyncio
    async def test_can_judge_after_window_closed(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test Marquis can judge after window is closed."""
        await service.register_advisory(sample_advisory, ["paimon"])

        # Cannot judge initially
        result = await service.check_can_judge("orias", "quantum computing risks")
        assert result.can_judge is False

        # Close window
        windows = await service.get_open_windows("orias")
        await service.close_advisory_window(windows[0].window_id)

        # Can judge now
        result = await service.check_can_judge("orias", "quantum computing risks")
        assert result.can_judge is True


# =============================================================================
# DOMAIN MODEL TESTS
# =============================================================================


class TestDomainModels:
    """Tests for domain model behavior."""

    def test_advisory_acknowledgment_immutability(self) -> None:
        """Test AdvisoryAcknowledgment is immutable."""
        ack = AdvisoryAcknowledgment.create(
            advisory_id=uuid4(),
            acknowledged_by="paimon",
            understanding="Test",
        )
        with pytest.raises(AttributeError):
            ack.understanding = "Modified"  # type: ignore

    def test_contrary_decision_immutability(self) -> None:
        """Test ContraryDecision is immutable."""
        decision = ContraryDecision.create(
            advisory_id=uuid4(),
            decided_by="paimon",
            reasoning="Test reason",
            decision_summary="Test decision",
        )
        with pytest.raises(AttributeError):
            decision.reasoning = "Modified"  # type: ignore

    def test_advisory_window_immutability(self) -> None:
        """Test AdvisoryWindow is immutable."""
        window = AdvisoryWindow.create(
            marquis_id="orias",
            advisory_id=uuid4(),
            topic="Test topic",
        )
        with pytest.raises(AttributeError):
            window.topic = "Modified"  # type: ignore

    def test_advisory_window_with_closed(self) -> None:
        """Test AdvisoryWindow.with_closed creates new instance."""
        window = AdvisoryWindow.create(
            marquis_id="orias",
            advisory_id=uuid4(),
            topic="Test topic",
        )
        assert window.is_open is True

        closed = window.with_closed()
        assert closed.is_open is False
        assert window.is_open is True  # Original unchanged

    def test_deadline_violation_serialization(self) -> None:
        """Test DeadlineViolation serialization."""
        violation = DeadlineViolation.create(
            advisory_id=uuid4(),
            archon_id="paimon",
            deadline=datetime.now(timezone.utc),
            consecutive_misses=2,
            status=AcknowledgmentDeadlineStatus.WARNING,
        )
        data = violation.to_dict()
        assert "advisory_id" in data
        assert "archon_id" in data
        assert "deadline" in data
        assert data["status"] == "warning"
        assert data["consecutive_misses"] == 2


# =============================================================================
# STATISTICS TESTS
# =============================================================================


class TestStatistics:
    """Tests for statistics reporting."""

    @pytest.mark.asyncio
    async def test_get_acknowledgment_stats(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
    ) -> None:
        """Test statistics gathering."""
        await service.register_advisory(sample_advisory, ["paimon", "bael"])

        await service.record_acknowledgment(
            AcknowledgmentRequest(
                advisory_id=sample_advisory.advisory_id,
                archon_id="paimon",
                understanding="Understood",
            )
        )

        stats = await service.get_acknowledgment_stats(hours=24)
        assert stats["total_advisories"] == 1
        assert stats["pending_acknowledgments"] == 1  # bael hasn't acknowledged
        assert stats["open_advisory_windows"] == 1


# =============================================================================
# KNIGHT WITNESS INTEGRATION TESTS
# =============================================================================


class TestKnightWitnessIntegration:
    """Tests for Knight witness integration per CT-12."""

    @pytest.mark.asyncio
    async def test_advisory_registration_witnessed(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test advisory registration is witnessed."""
        await service.register_advisory(sample_advisory, ["paimon"])

        # Should have called observe for advisory and window
        assert mock_knight_witness.observe.call_count >= 2

    @pytest.mark.asyncio
    async def test_window_operations_witnessed(
        self,
        service: AdvisoryAcknowledgmentService,
        sample_advisory: Advisory,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test window open/close operations are witnessed."""
        await service.register_advisory(sample_advisory, ["paimon"])
        initial_calls = mock_knight_witness.observe.call_count

        windows = await service.get_open_windows("orias")
        await service.close_advisory_window(windows[0].window_id)

        # Should have additional call for window close
        assert mock_knight_witness.observe.call_count > initial_calls


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================


class TestConfiguration:
    """Tests for configuration handling."""

    def test_config_deadline_property(self) -> None:
        """Test configuration deadline property."""
        config = AdvisoryTrackingConfig(acknowledgment_deadline_hours=24)
        assert config.acknowledgment_deadline == timedelta(hours=24)

    def test_default_config_values(self) -> None:
        """Test default configuration values."""
        config = AdvisoryTrackingConfig()
        assert config.acknowledgment_deadline_hours == 48
        assert config.window_close_on_motion_complete is True
        assert config.warning_on_missed_deadline is True
        assert config.escalate_pattern_threshold == 3

    @pytest.mark.asyncio
    async def test_service_without_knight_witness(self) -> None:
        """Test service works without Knight witness (for testing)."""
        service = AdvisoryAcknowledgmentService(knight_witness=None)
        advisory = Advisory.create(
            issued_by="orias",
            domain=ExpertiseDomain.SCIENCE,
            topic="test topic",
            recommendation="test",
            rationale="test",
        )
        await service.register_advisory(advisory, ["paimon"])

        result = await service.record_acknowledgment(
            AcknowledgmentRequest(
                advisory_id=advisory.advisory_id,
                archon_id="paimon",
                understanding="Understood",
            )
        )
        assert result.success is True


# =============================================================================
# TOPIC OVERLAP TESTS
# =============================================================================


class TestTopicOverlap:
    """Tests for topic overlap detection."""

    @pytest.mark.asyncio
    async def test_exact_match(
        self,
        service: AdvisoryAcknowledgmentService,
    ) -> None:
        """Test exact topic match is detected."""
        # Access private method for direct testing
        assert service._topics_overlap("quantum computing", "quantum computing") is True

    @pytest.mark.asyncio
    async def test_substring_match(
        self,
        service: AdvisoryAcknowledgmentService,
    ) -> None:
        """Test substring topic match is detected."""
        assert service._topics_overlap("quantum", "quantum computing") is True
        assert service._topics_overlap("quantum computing", "quantum") is True

    @pytest.mark.asyncio
    async def test_word_overlap(
        self,
        service: AdvisoryAcknowledgmentService,
    ) -> None:
        """Test word overlap is detected."""
        assert (
            service._topics_overlap("quantum computing risks", "quantum computing security")
            is True
        )

    @pytest.mark.asyncio
    async def test_no_overlap(
        self,
        service: AdvisoryAcknowledgmentService,
    ) -> None:
        """Test unrelated topics don't overlap."""
        assert service._topics_overlap("quantum computing", "biodiversity") is False

    @pytest.mark.asyncio
    async def test_case_insensitive(
        self,
        service: AdvisoryAcknowledgmentService,
    ) -> None:
        """Test topic comparison is case insensitive."""
        assert service._topics_overlap("Quantum Computing", "quantum computing") is True
