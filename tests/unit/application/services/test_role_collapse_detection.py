"""Unit tests for Role Collapse Detection Service (Epic 8, Story 8.4).

Tests per acceptance criteria:
- AC1: Role collapse detection
- AC2: Role collapse rejection and witnessing
- AC3: Branch action tracking
- AC4: PRD §2.1 enforcement
- AC5: Branch conflict matrix integration (now via YAML loader per HARDENING-2)
- AC6: Violation severity classification
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.branch_action_tracker import (
    ArchonBranchHistory,
    BranchAction,
    GovernanceAction,
    GovernanceBranch,
    RecordActionRequest,
)
from src.application.services.role_collapse_detection_service import (
    CollapseCheckResult,
    RoleCollapseDetectionService,
    RoleCollapseError,
    RoleCollapseSeverity,
    RoleCollapseViolation,
)
from src.infrastructure.adapters.config.branch_conflict_rules_loader import (
    YamlBranchConflictRulesLoader,
)
from src.infrastructure.adapters.government.branch_action_tracker_adapter import (
    BranchActionTrackerAdapter,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tracker() -> BranchActionTrackerAdapter:
    """Create a fresh branch action tracker."""
    return BranchActionTrackerAdapter()


@pytest.fixture
def rules_loader() -> YamlBranchConflictRulesLoader:
    """Create a rules loader that loads from YAML.

    Per HARDENING-2: Rules are loaded from config/permissions/rank-matrix.yaml
    """
    return YamlBranchConflictRulesLoader()


@pytest.fixture
def service(
    tracker: BranchActionTrackerAdapter,
    rules_loader: YamlBranchConflictRulesLoader,
) -> RoleCollapseDetectionService:
    """Create a role collapse detection service with tracker and rules loader.

    Per HARDENING-2 AC6: Tests use the same YAML source as production.
    """
    return RoleCollapseDetectionService(tracker=tracker, rules_loader=rules_loader)


@pytest.fixture
def motion_id() -> UUID:
    """Generate a motion UUID."""
    return uuid4()


@pytest.fixture
def king_archon_id() -> str:
    """A King archon ID (legislative branch)."""
    return "king-paimon"


@pytest.fixture
def president_archon_id() -> str:
    """A President archon ID (executive branch)."""
    return "president-astaroth"


@pytest.fixture
def prince_archon_id() -> str:
    """A Prince archon ID (judicial branch)."""
    return "prince-orobas"


@pytest.fixture
def duke_archon_id() -> str:
    """A Duke archon ID (administrative branch)."""
    return "duke-eligos"


@pytest.fixture
def marquis_archon_id() -> str:
    """A Marquis archon ID (advisory branch)."""
    return "marquis-samigina"


# =============================================================================
# AC3: Branch Action Tracking Tests
# =============================================================================


class TestBranchActionTracking:
    """Tests for AC3: Branch action tracking."""

    @pytest.mark.asyncio
    async def test_record_branch_action_success(
        self,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test that branch actions are recorded with all required fields."""
        # Record an action
        request = RecordActionRequest(
            archon_id=king_archon_id,
            motion_id=motion_id,
            action_type=GovernanceAction.INTRODUCE_MOTION,
            branch=GovernanceBranch.LEGISLATIVE,
        )
        result = await tracker.record_branch_action(request)

        # Verify success
        assert result.success is True
        assert result.action is not None

        # Verify all required fields per AC3
        action = result.action
        assert action.archon_id == king_archon_id
        assert action.motion_id == motion_id
        assert action.branch == GovernanceBranch.LEGISLATIVE
        assert action.action_type == GovernanceAction.INTRODUCE_MOTION
        assert action.acted_at is not None
        assert action.action_id is not None

    @pytest.mark.asyncio
    async def test_record_multiple_actions_same_motion(
        self,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test recording multiple actions on the same motion."""
        # Record actions from different archons
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon-1",
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon-2",
                motion_id=motion_id,
                action_type=GovernanceAction.DEFINE_EXECUTION,
                branch=GovernanceBranch.EXECUTIVE,
            )
        )

        # Get all actions
        actions = await tracker.get_motion_actions(motion_id)
        assert len(actions) == 2

    @pytest.mark.asyncio
    async def test_get_archon_branches(
        self,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test getting branches an archon has acted in."""
        # Record an action
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        # Get branches
        branches = await tracker.get_archon_branches(king_archon_id, motion_id)
        assert len(branches) == 1
        assert GovernanceBranch.LEGISLATIVE in branches

    @pytest.mark.asyncio
    async def test_get_archon_history(
        self,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test getting full archon action history."""
        # Record actions
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.DELIBERATE,
                branch=GovernanceBranch.DELIBERATIVE,
            )
        )

        # Get history
        history = await tracker.get_archon_history(king_archon_id, motion_id)
        assert history is not None
        assert history.archon_id == king_archon_id
        assert history.motion_id == motion_id
        assert len(history.actions) == 2
        assert history.branch_count == 2

    @pytest.mark.asyncio
    async def test_has_acted_in_branch(
        self,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test checking if archon has acted in specific branch."""
        # Record action
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        # Check
        assert (
            await tracker.has_acted_in_branch(
                king_archon_id, motion_id, GovernanceBranch.LEGISLATIVE
            )
            is True
        )
        assert (
            await tracker.has_acted_in_branch(
                king_archon_id, motion_id, GovernanceBranch.EXECUTIVE
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_branch_derived_from_action(
        self,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test that branch is derived from action type when not specified."""
        # Record without specifying branch
        request = RecordActionRequest(
            archon_id="archon-1",
            motion_id=motion_id,
            action_type=GovernanceAction.JUDGE,
            # branch not specified
        )
        result = await tracker.record_branch_action(request)

        assert result.success is True
        assert result.action is not None
        assert result.action.branch == GovernanceBranch.JUDICIAL


# =============================================================================
# AC1: Role Collapse Detection Tests
# =============================================================================


class TestRoleCollapseDetection:
    """Tests for AC1: Role collapse detection."""

    @pytest.mark.asyncio
    async def test_detect_no_collapse_new_archon(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test no collapse for archon with no previous actions."""
        result = await service.detect_collapse(
            archon_id=king_archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.LEGISLATIVE,
        )

        assert result.has_collapse is False
        assert result.violation is None
        assert result.message == "No role collapse detected"

    @pytest.mark.asyncio
    async def test_detect_no_collapse_same_branch(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test no collapse when acting multiple times in same branch."""
        # Record first action
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        # Try to act again in same branch
        result = await service.detect_collapse(
            archon_id=king_archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.LEGISLATIVE,
        )

        assert result.has_collapse is False

    @pytest.mark.asyncio
    async def test_detect_collapse_legislative_executive(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test collapse detection for legislative→executive (King→President)."""
        # King introduces motion (legislative)
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        # Same archon tries to define execution (executive)
        result = await service.detect_collapse(
            archon_id=king_archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        assert result.has_collapse is True
        assert result.violation is not None
        assert "WHAT and HOW" in result.violation.conflict_rule
        assert result.violation.severity == RoleCollapseSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_detect_collapse_executive_judicial(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        president_archon_id: str,
    ) -> None:
        """Test collapse detection for executive→judicial (President→Prince)."""
        # President defines execution
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=president_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.DEFINE_EXECUTION,
                branch=GovernanceBranch.EXECUTIVE,
            )
        )

        # Same archon tries to judge compliance
        result = await service.detect_collapse(
            archon_id=president_archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.JUDICIAL,
        )

        assert result.has_collapse is True
        assert result.violation is not None
        assert "judge" in result.violation.conflict_rule.lower()
        assert result.violation.severity == RoleCollapseSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_detect_collapse_advisory_judicial(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        marquis_archon_id: str,
    ) -> None:
        """Test collapse detection for advisory→judicial (Marquis→Prince)."""
        # Marquis advises
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=marquis_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.ADVISE,
                branch=GovernanceBranch.ADVISORY,
            )
        )

        # Same archon tries to judge
        result = await service.detect_collapse(
            archon_id=marquis_archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.JUDICIAL,
        )

        assert result.has_collapse is True
        assert result.violation is not None
        assert result.violation.severity == RoleCollapseSeverity.MAJOR  # Per AC6

    @pytest.mark.asyncio
    async def test_detect_collapse_includes_archon_motion_roles(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test that violation includes archon, motion, and roles per AC1."""
        # Set up collapse scenario
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        result = await service.detect_collapse(
            archon_id=king_archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        assert result.has_collapse is True
        violation = result.violation
        assert violation is not None

        # AC1: Includes identification of archon, roles, and motion
        assert violation.archon_id == king_archon_id
        assert violation.motion_id == motion_id
        assert GovernanceBranch.LEGISLATIVE in violation.existing_branches
        assert violation.attempted_branch == GovernanceBranch.EXECUTIVE
        assert len(violation.collapsed_roles) >= 1


# =============================================================================
# AC2: Role Collapse Rejection Tests
# =============================================================================


class TestRoleCollapseRejection:
    """Tests for AC2: Role collapse rejection and witnessing."""

    @pytest.mark.asyncio
    async def test_enforce_no_collapse_raises_on_violation(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test that enforce_no_collapse raises RoleCollapseError on violation."""
        # Set up collapse scenario
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        # Should raise
        with pytest.raises(RoleCollapseError) as exc_info:
            await service.enforce_no_collapse(
                archon_id=king_archon_id,
                motion_id=motion_id,
                proposed_branch=GovernanceBranch.EXECUTIVE,
            )

        error = exc_info.value
        assert error.violation is not None
        assert error.error_code == "ROLE_COLLAPSE_VIOLATION"

    @pytest.mark.asyncio
    async def test_enforce_no_collapse_returns_result_on_success(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test that enforce_no_collapse returns result when no violation."""
        result = await service.enforce_no_collapse(
            archon_id=king_archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.LEGISLATIVE,
        )

        assert result.has_collapse is False

    @pytest.mark.asyncio
    async def test_violation_marked_as_rejected(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test that violations are marked as rejected per AC2."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        result = await service.detect_collapse(
            archon_id=king_archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        assert result.violation is not None
        assert result.violation.rejected is True

    @pytest.mark.asyncio
    async def test_violation_includes_role_boundaries(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test that rejection includes specific role boundaries violated per AC2."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        result = await service.detect_collapse(
            archon_id=king_archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        assert result.violation is not None
        # Should have conflict rule describing the boundary
        assert result.violation.conflict_rule is not None
        assert len(result.violation.conflict_rule) > 0

    @pytest.mark.asyncio
    async def test_error_response_format(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        king_archon_id: str,
    ) -> None:
        """Test that RoleCollapseError produces correct HTTP response format."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=king_archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        try:
            await service.enforce_no_collapse(
                archon_id=king_archon_id,
                motion_id=motion_id,
                proposed_branch=GovernanceBranch.EXECUTIVE,
            )
            pytest.fail("Should have raised RoleCollapseError")
        except RoleCollapseError as e:
            response = e.to_error_response()

            assert response["error_code"] == "ROLE_COLLAPSE_VIOLATION"
            assert "prd_reference" in response
            assert response["archon_id"] == king_archon_id
            assert response["motion_id"] == str(motion_id)
            assert "existing_branches" in response
            assert "attempted_branch" in response
            assert "conflict_rule" in response
            assert "severity" in response


# =============================================================================
# AC4: PRD §2.1 Enforcement Tests
# =============================================================================


class TestPRDSection21Enforcement:
    """Tests for AC4: PRD §2.1 enforcement - No entity may define intent, execute it, AND judge it."""

    @pytest.mark.asyncio
    async def test_king_cannot_become_president(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test King who introduced motion cannot define execution."""
        archon_id = "archon-attempting-collapse"

        # Act as King (introduce motion)
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        # Try to act as President (define execution)
        result = await service.detect_collapse(
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        assert result.has_collapse is True
        assert "PRD §2.1" in result.violation.prd_reference

    @pytest.mark.asyncio
    async def test_president_cannot_become_prince(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test President who planned execution cannot judge compliance."""
        archon_id = "archon-attempting-collapse"

        # Act as President
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.DEFINE_EXECUTION,
                branch=GovernanceBranch.EXECUTIVE,
            )
        )

        # Try to act as Prince
        result = await service.detect_collapse(
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.JUDICIAL,
        )

        assert result.has_collapse is True

    @pytest.mark.asyncio
    async def test_duke_cannot_become_prince(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test Duke who executed cannot judge their own execution."""
        archon_id = "archon-attempting-collapse"

        # Act as Duke
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.EXECUTE,
                branch=GovernanceBranch.ADMINISTRATIVE,
            )
        )

        # Try to act as Prince
        result = await service.detect_collapse(
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.JUDICIAL,
        )

        assert result.has_collapse is True

    @pytest.mark.asyncio
    async def test_king_cannot_become_prince(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test King who introduced motion cannot judge it."""
        archon_id = "archon-attempting-collapse"

        # Act as King
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id=archon_id,
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        # Try to act as Prince
        result = await service.detect_collapse(
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.JUDICIAL,
        )

        assert result.has_collapse is True


# =============================================================================
# AC5: Branch Conflict Matrix Integration Tests
# =============================================================================


class TestBranchConflictMatrix:
    """Tests for AC5: Branch conflict matrix integration.

    Per HARDENING-2: Rules are now loaded from YAML via BranchConflictRulesLoader.
    Tests validate the actual YAML configuration (AC6: tests use same source).
    """

    def test_conflict_rules_loaded_from_yaml(
        self,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test that conflict rules are loaded from YAML."""
        rules = rules_loader.load_rules()
        assert len(rules) > 0

    def test_legislative_executive_conflict_rule_in_yaml(
        self,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test legislative↔executive conflict rule exists in YAML."""
        rule = rules_loader.get_rule_by_id("legislative_executive")
        assert rule is not None
        assert "WHAT and HOW" in rule.rule
        assert rule.severity == "critical"

    def test_executive_judicial_conflict_rule_in_yaml(
        self,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test executive↔judicial conflict rule exists in YAML."""
        rule = rules_loader.get_rule_by_id("executive_judicial")
        assert rule is not None
        assert "judge" in rule.rule.lower()
        assert rule.severity == "critical"

    def test_advisory_judicial_conflict_rule_in_yaml(
        self,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test advisory↔judicial conflict rule exists in YAML."""
        rule = rules_loader.get_rule_by_id("advisory_judicial")
        assert rule is not None
        assert "advised" in rule.rule.lower()
        assert rule.severity == "major"

    def test_legislative_judicial_conflict_rule_in_yaml(
        self,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test legislative↔judicial conflict rule exists in YAML."""
        rule = rules_loader.get_rule_by_id("legislative_judicial")
        assert rule is not None
        assert rule.severity == "critical"

    def test_administrative_judicial_conflict_rule_in_yaml(
        self,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test administrative↔judicial conflict rule exists in YAML."""
        rule = rules_loader.get_rule_by_id("administrative_judicial")
        assert rule is not None
        assert rule.severity == "critical"

    def test_no_conflict_between_non_conflicting_branches(
        self,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test no conflict rule for branches that don't conflict."""
        rules = rules_loader.load_rules()
        # Find a rule that applies to legislative and advisory
        for rule in rules:
            if rule.applies_to("legislative", "advisory"):
                pytest.fail(
                    f"Unexpected conflict rule between legislative and advisory: {rule.id}"
                )

    def test_witness_branch_has_no_active_conflicts(
        self,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test witness branch conflict rules are informational only."""
        rule = rules_loader.get_rule_by_id("witness_exclusion")
        assert rule is not None
        # Witness rule should be info severity (not enforceable conflict)
        assert rule.severity == "info"
        # Witness rule has only one branch (doesn't conflict with others)
        assert len(rule.branches) == 1

    @pytest.mark.asyncio
    async def test_violation_references_conflict_rule(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test that violations reference the specific conflict rule."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon",
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        result = await service.detect_collapse(
            archon_id="archon",
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        assert result.violation is not None
        # Should reference the specific rule from YAML
        expected_rule = rules_loader.get_rule_by_id("legislative_executive")
        assert result.violation.conflict_rule == expected_rule.rule


# =============================================================================
# AC6: Violation Severity Classification Tests
# =============================================================================


class TestViolationSeverityClassification:
    """Tests for AC6: Violation severity classification."""

    @pytest.mark.asyncio
    async def test_legislative_executive_is_critical(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test legislative↔executive collapse is CRITICAL severity."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon",
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        result = await service.detect_collapse(
            archon_id="archon",
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        assert result.violation is not None
        assert result.violation.severity == RoleCollapseSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_executive_judicial_is_critical(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test executive↔judicial collapse is CRITICAL severity."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon",
                motion_id=motion_id,
                action_type=GovernanceAction.DEFINE_EXECUTION,
                branch=GovernanceBranch.EXECUTIVE,
            )
        )

        result = await service.detect_collapse(
            archon_id="archon",
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.JUDICIAL,
        )

        assert result.violation is not None
        assert result.violation.severity == RoleCollapseSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_advisory_judicial_is_major(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test advisory↔judicial collapse is MAJOR severity."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon",
                motion_id=motion_id,
                action_type=GovernanceAction.ADVISE,
                branch=GovernanceBranch.ADVISORY,
            )
        )

        result = await service.detect_collapse(
            archon_id="archon",
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.JUDICIAL,
        )

        assert result.violation is not None
        assert result.violation.severity == RoleCollapseSeverity.MAJOR

    @pytest.mark.asyncio
    async def test_all_role_collapse_requires_conclave_review(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test all role collapse violations require Conclave review per AC6."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon",
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        result = await service.detect_collapse(
            archon_id="archon",
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        assert result.violation is not None
        assert result.violation.escalated_to_conclave is True


# =============================================================================
# Audit Trail Tests
# =============================================================================


class TestAuditTrail:
    """Tests for audit trail functionality."""

    @pytest.mark.asyncio
    async def test_violations_stored_for_audit(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test that violations are stored for audit trail."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon",
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        await service.detect_collapse(
            archon_id="archon",
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        violations = service.get_violations(motion_id=motion_id)
        assert len(violations) == 1

    @pytest.mark.asyncio
    async def test_audit_entry_created(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test that audit entry can be created for violations."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon",
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        result = await service.detect_collapse(
            archon_id="archon",
            motion_id=motion_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        # Create audit entry
        entry = service.record_audit_entry(
            violation=result.violation,
            witness_statement_id=uuid4(),
        )

        assert entry is not None
        assert entry.violation == result.violation

        # Retrieve audit entries
        entries = service.get_audit_entries(motion_id=motion_id)
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_filter_violations_by_archon(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
    ) -> None:
        """Test filtering violations by archon."""
        motion_id_1 = uuid4()
        motion_id_2 = uuid4()

        # Create violations for different archons
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon-1",
                motion_id=motion_id_1,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )
        await service.detect_collapse(
            archon_id="archon-1",
            motion_id=motion_id_1,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon-2",
                motion_id=motion_id_2,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )
        await service.detect_collapse(
            archon_id="archon-2",
            motion_id=motion_id_2,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        # Filter by archon
        archon_1_violations = service.get_violations(archon_id="archon-1")
        assert len(archon_1_violations) == 1
        assert archon_1_violations[0].archon_id == "archon-1"


# =============================================================================
# Record Action If Allowed Tests
# =============================================================================


class TestRecordActionIfAllowed:
    """Tests for the combined check-and-record method."""

    @pytest.mark.asyncio
    async def test_records_action_when_no_collapse(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test that action is recorded when no collapse detected."""
        await service.record_action_if_allowed(
            archon_id="archon",
            motion_id=motion_id,
            action=GovernanceAction.INTRODUCE_MOTION,
        )

        # Verify action was recorded
        branches = await tracker.get_archon_branches("archon", motion_id)
        assert GovernanceBranch.LEGISLATIVE in branches

    @pytest.mark.asyncio
    async def test_raises_error_when_collapse_detected(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test that error is raised and action NOT recorded on collapse."""
        # First action
        await service.record_action_if_allowed(
            archon_id="archon",
            motion_id=motion_id,
            action=GovernanceAction.INTRODUCE_MOTION,
        )

        # Collapsing action should raise
        with pytest.raises(RoleCollapseError):
            await service.record_action_if_allowed(
                archon_id="archon",
                motion_id=motion_id,
                action=GovernanceAction.DEFINE_EXECUTION,
            )

        # Verify collapsing action was NOT recorded
        branches = await tracker.get_archon_branches("archon", motion_id)
        assert GovernanceBranch.EXECUTIVE not in branches


# =============================================================================
# Detect Collapse For Action Tests
# =============================================================================


class TestDetectCollapseForAction:
    """Tests for convenience method that detects collapse from action."""

    @pytest.mark.asyncio
    async def test_detect_collapse_for_action_derives_branch(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
        motion_id: UUID,
    ) -> None:
        """Test that branch is correctly derived from action."""
        await tracker.record_branch_action(
            RecordActionRequest(
                archon_id="archon",
                motion_id=motion_id,
                action_type=GovernanceAction.INTRODUCE_MOTION,
                branch=GovernanceBranch.LEGISLATIVE,
            )
        )

        result = await service.detect_collapse_for_action(
            archon_id="archon",
            motion_id=motion_id,
            proposed_action=GovernanceAction.DEFINE_EXECUTION,  # Executive branch action
        )

        assert result.has_collapse is True
        assert result.proposed_branch == GovernanceBranch.EXECUTIVE


# =============================================================================
# Domain Model Tests
# =============================================================================


class TestDomainModels:
    """Tests for domain models."""

    def test_branch_action_to_dict(self) -> None:
        """Test BranchAction serialization."""
        action = BranchAction.create(
            archon_id="archon",
            motion_id=uuid4(),
            branch=GovernanceBranch.LEGISLATIVE,
            action_type=GovernanceAction.INTRODUCE_MOTION,
            timestamp=datetime.now(timezone.utc),  # Per HARDENING-1
        )

        data = action.to_dict()
        assert "action_id" in data
        assert data["archon_id"] == "archon"
        assert data["branch"] == "legislative"
        assert data["action_type"] == "introduce_motion"

    def test_role_collapse_violation_to_dict(
        self,
        rules_loader: YamlBranchConflictRulesLoader,
    ) -> None:
        """Test RoleCollapseViolation serialization.

        Per HARDENING-2: Violations are created by the service, not directly.
        This test uses direct instantiation for serialization testing.
        """
        # Load a rule from YAML to get correct format
        rule = rules_loader.get_rule_by_id("legislative_executive")

        violation = RoleCollapseViolation(
            violation_id=uuid4(),
            archon_id="archon",
            motion_id=uuid4(),
            existing_branches=(GovernanceBranch.LEGISLATIVE,),
            attempted_branch=GovernanceBranch.EXECUTIVE,
            collapsed_roles=(),
            conflict_rule=rule.rule,
            prd_reference=rule.prd_ref,
            severity=RoleCollapseSeverity.CRITICAL,
            detected_at=datetime.now(timezone.utc),
        )

        data = violation.to_dict()
        assert data["violation_type"] == "ROLE_COLLAPSE_VIOLATION"
        assert data["archon_id"] == "archon"
        assert "existing_branches" in data
        assert "attempted_branch" in data
        assert "severity" in data

    def test_collapse_check_result_to_dict(self) -> None:
        """Test CollapseCheckResult serialization."""
        result = CollapseCheckResult.no_collapse(
            archon_id="archon",
            motion_id=uuid4(),
            proposed_branch=GovernanceBranch.LEGISLATIVE,
        )

        data = result.to_dict()
        assert data["has_collapse"] is False
        assert data["archon_id"] == "archon"

    def test_archon_branch_history_properties(self) -> None:
        """Test ArchonBranchHistory properties."""
        motion_id = uuid4()
        action = BranchAction.create(
            archon_id="archon",
            motion_id=motion_id,
            branch=GovernanceBranch.LEGISLATIVE,
            action_type=GovernanceAction.INTRODUCE_MOTION,
            timestamp=datetime.now(timezone.utc),  # Per HARDENING-1
        )

        history = ArchonBranchHistory.create(
            archon_id="archon",
            motion_id=motion_id,
            actions=[action],
            timestamp=datetime.now(timezone.utc),  # Per HARDENING-1
        )

        assert history.branch_count == 1
        assert history.has_acted_in_branch(GovernanceBranch.LEGISLATIVE) is True
        assert history.has_acted_in_branch(GovernanceBranch.EXECUTIVE) is False


# =============================================================================
# Integration Scenario Tests
# =============================================================================


class TestIntegrationScenarios:
    """Integration tests for complete workflow scenarios."""

    @pytest.mark.asyncio
    async def test_scenario_king_to_president_blocked(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
    ) -> None:
        """
        Scenario 1: King → President (CRITICAL)
        A King introduces a motion, motion is ratified, then the same
        King tries to act as President and define execution.
        Expected: BLOCKED
        """
        motion_id = uuid4()
        archon_id = "paimon-attempting-collapse"

        # King introduces motion
        await service.record_action_if_allowed(
            archon_id=archon_id,
            motion_id=motion_id,
            action=GovernanceAction.INTRODUCE_MOTION,
        )

        # Later, same archon tries to define execution
        with pytest.raises(RoleCollapseError) as exc_info:
            await service.record_action_if_allowed(
                archon_id=archon_id,
                motion_id=motion_id,
                action=GovernanceAction.DEFINE_EXECUTION,
            )

        assert exc_info.value.violation.severity == RoleCollapseSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_scenario_president_to_prince_blocked(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
    ) -> None:
        """
        Scenario 2: President → Prince (CRITICAL)
        A President plans execution, execution completes, then the same
        President tries to judge compliance.
        Expected: BLOCKED
        """
        motion_id = uuid4()
        archon_id = "astaroth-attempting-collapse"

        # President defines execution
        await service.record_action_if_allowed(
            archon_id=archon_id,
            motion_id=motion_id,
            action=GovernanceAction.DEFINE_EXECUTION,
        )

        # Later, same archon tries to judge
        with pytest.raises(RoleCollapseError) as exc_info:
            await service.record_action_if_allowed(
                archon_id=archon_id,
                motion_id=motion_id,
                action=GovernanceAction.JUDGE,
            )

        assert exc_info.value.violation.severity == RoleCollapseSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_scenario_marquis_to_prince_blocked(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
    ) -> None:
        """
        Scenario 3: Marquis → Prince (MAJOR)
        A Marquis advises on topic X, then tries to judge on topic X.
        Expected: BLOCKED (but MAJOR severity, not CRITICAL)
        """
        motion_id = uuid4()
        archon_id = "samigina-attempting-collapse"

        # Marquis advises
        await service.record_action_if_allowed(
            archon_id=archon_id,
            motion_id=motion_id,
            action=GovernanceAction.ADVISE,
        )

        # Later, same archon tries to judge
        with pytest.raises(RoleCollapseError) as exc_info:
            await service.record_action_if_allowed(
                archon_id=archon_id,
                motion_id=motion_id,
                action=GovernanceAction.JUDGE,
            )

        # Should be MAJOR, not CRITICAL
        assert exc_info.value.violation.severity == RoleCollapseSeverity.MAJOR

    @pytest.mark.asyncio
    async def test_scenario_different_archons_allowed(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
    ) -> None:
        """
        Scenario: Different archons can act in different branches on same motion.
        King introduces, different President defines, different Prince judges.
        Expected: ALLOWED
        """
        motion_id = uuid4()

        # King introduces
        await service.record_action_if_allowed(
            archon_id="king-paimon",
            motion_id=motion_id,
            action=GovernanceAction.INTRODUCE_MOTION,
        )

        # Different President defines
        await service.record_action_if_allowed(
            archon_id="president-astaroth",
            motion_id=motion_id,
            action=GovernanceAction.DEFINE_EXECUTION,
        )

        # Different Prince judges
        await service.record_action_if_allowed(
            archon_id="prince-orobas",
            motion_id=motion_id,
            action=GovernanceAction.JUDGE,
        )

        # All should succeed - verify no violations
        violations = service.get_violations(motion_id=motion_id)
        assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_scenario_same_archon_multiple_motions_allowed(
        self,
        service: RoleCollapseDetectionService,
        tracker: BranchActionTrackerAdapter,
    ) -> None:
        """
        Scenario: Same archon can act as King on one motion and President on another.
        Expected: ALLOWED (role collapse is per-motion)
        """
        motion_id_1 = uuid4()
        motion_id_2 = uuid4()
        archon_id = "multi-capable-archon"

        # Act as King on motion 1
        await service.record_action_if_allowed(
            archon_id=archon_id,
            motion_id=motion_id_1,
            action=GovernanceAction.INTRODUCE_MOTION,
        )

        # Act as President on motion 2 (different motion - should be allowed)
        await service.record_action_if_allowed(
            archon_id=archon_id,
            motion_id=motion_id_2,
            action=GovernanceAction.DEFINE_EXECUTION,
        )

        # Both should succeed
        violations = service.get_violations()
        assert len(violations) == 0
