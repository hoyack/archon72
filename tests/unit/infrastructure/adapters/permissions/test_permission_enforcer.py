"""Unit tests for Permission Enforcer Adapter.

Tests the rank-based permission enforcement per Government PRD §10.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from src.application.ports.permission_enforcer import (
    GovernanceAction,
    GovernanceBranch,
    PermissionContext,
    RankViolationError,
    ViolationSeverity,
)
from src.infrastructure.adapters.permissions.permission_enforcer_adapter import (
    PermissionEnforcerAdapter,
    create_permission_enforcer,
)


@pytest.fixture
def config_path() -> Path:
    """Get the path to the rank-matrix.yaml config."""
    return Path("config/permissions/rank-matrix.yaml")


@pytest.fixture
def enforcer(config_path: Path) -> PermissionEnforcerAdapter:
    """Create a permission enforcer with the real config."""
    return PermissionEnforcerAdapter(config_path=config_path, verbose=True)


class TestPermissionEnforcerInit:
    """Tests for PermissionEnforcerAdapter initialization."""

    def test_loads_config_successfully(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that the enforcer loads the YAML config.

        Per rank-matrix.yaml v2.0: Ranks are keyed on original_rank (constitutional role).
        """
        # Should have loaded ranks keyed on original_rank
        assert len(enforcer._ranks) > 0
        assert "King" in enforcer._ranks
        assert "Knight" in enforcer._ranks
        assert "Prince" in enforcer._ranks
        assert "Duke" in enforcer._ranks

    def test_factory_function_creates_enforcer(self, config_path: Path) -> None:
        """Test the factory function works."""
        enforcer = create_permission_enforcer(config_path=config_path)
        assert enforcer is not None

    def test_raises_on_missing_config(self, tmp_path: Path) -> None:
        """Test that missing config raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            PermissionEnforcerAdapter(config_path=tmp_path / "nonexistent.yaml")


class TestKingPermissions:
    """Tests for King (executive_director) rank permissions.

    Per PRD §4.1: Kings may introduce motions and define WHAT.
    Per PRD FR-GOV-6: Kings may NOT define HOW.
    """

    def test_king_can_introduce_motion(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Kings can introduce motions."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Paimon",
            aegis_rank="executive_director",
            original_rank="King",
            branch="legislative",
            action=GovernanceAction.INTRODUCE_MOTION,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True

    def test_king_can_deliberate(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Kings can participate in deliberation."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Belial",
            aegis_rank="executive_director",
            original_rank="King",
            branch="legislative",
            action=GovernanceAction.DELIBERATE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True

    def test_king_can_ratify(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Kings can vote on ratification."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Asmoday",
            aegis_rank="executive_director",
            original_rank="King",
            branch="legislative",
            action=GovernanceAction.RATIFY,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True

    def test_king_cannot_define_execution(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Kings cannot define HOW (execution).

        Per FR-GOV-6: Kings may NOT define tasks, timelines, tools, execution methods.
        """
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Paimon",
            aegis_rank="executive_director",
            original_rank="King",
            branch="legislative",
            action=GovernanceAction.DEFINE_EXECUTION,
        )
        result = enforcer.check_permission(context)

        assert result.allowed is False
        assert "prohibited" in result.violation_reason.lower()
        assert len(result.violation_details) > 0
        assert result.violation_details[0].severity == ViolationSeverity.MAJOR

    def test_king_cannot_execute(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Kings cannot execute tasks."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Belial",
            aegis_rank="executive_director",
            original_rank="King",
            branch="legislative",
            action=GovernanceAction.EXECUTE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False

    def test_king_cannot_judge(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Kings cannot judge compliance."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Asmoday",
            aegis_rank="executive_director",
            original_rank="King",
            branch="legislative",
            action=GovernanceAction.JUDGE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False


class TestPresidentPermissions:
    """Tests for President (senior_director) rank permissions.

    Per PRD §4.3: Presidents translate WHAT into HOW.
    """

    def test_president_can_define_execution(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Presidents can define execution plans."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Marbas",
            aegis_rank="senior_director",
            original_rank="President",
            branch="executive",
            action=GovernanceAction.DEFINE_EXECUTION,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True

    def test_president_can_deliberate(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Presidents can deliberate."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Marbas",
            aegis_rank="senior_director",
            original_rank="President",
            branch="executive",
            action=GovernanceAction.DELIBERATE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True

    def test_president_cannot_introduce_motion(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Presidents cannot introduce motions."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Marbas",
            aegis_rank="senior_director",
            original_rank="President",
            branch="executive",
            action=GovernanceAction.INTRODUCE_MOTION,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False


class TestPrincePermissions:
    """Tests for Prince (associate_director) rank permissions.

    Per PRD §4.5: Princes evaluate compliance.
    Per PRD FR-GOV-16: Princes may not introduce motions or define execution.
    """

    def test_prince_can_judge(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Princes can judge compliance."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Sitri",
            aegis_rank="associate_director",
            original_rank="Prince",
            branch="judicial",
            action=GovernanceAction.JUDGE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True

    def test_prince_cannot_introduce_motion(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Princes cannot introduce motions.

        Per FR-GOV-16.
        """
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Sitri",
            aegis_rank="associate_director",
            original_rank="Prince",
            branch="judicial",
            action=GovernanceAction.INTRODUCE_MOTION,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False

    def test_prince_cannot_define_execution(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Princes cannot define execution.

        Per FR-GOV-16.
        """
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Sitri",
            aegis_rank="associate_director",
            original_rank="Prince",
            branch="judicial",
            action=GovernanceAction.DEFINE_EXECUTION,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False


class TestKnightWitnessPermissions:
    """Tests for Knight/Furcas (observer) rank permissions.

    Per PRD §5: Knight exists outside all branches.
    Per PRD FR-GOV-21: Knight may not propose, debate, define execution, judge, or enforce.
    """

    def test_knight_can_witness(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Knight can witness (only permitted action)."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Furcas",
            aegis_rank="observer",
            original_rank="Knight",
            branch="witness",
            action=GovernanceAction.WITNESS,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True

    def test_knight_cannot_introduce_motion(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Knight cannot propose motions."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Furcas",
            aegis_rank="observer",
            original_rank="Knight",
            branch="witness",
            action=GovernanceAction.INTRODUCE_MOTION,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False

    def test_knight_cannot_deliberate(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Knight cannot debate."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Furcas",
            aegis_rank="observer",
            original_rank="Knight",
            branch="witness",
            action=GovernanceAction.DELIBERATE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False

    def test_knight_cannot_ratify(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Knight cannot vote on ratification."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Furcas",
            aegis_rank="observer",
            original_rank="Knight",
            branch="witness",
            action=GovernanceAction.RATIFY,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False

    def test_knight_cannot_judge(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Knight cannot judge compliance."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Furcas",
            aegis_rank="observer",
            original_rank="Knight",
            branch="witness",
            action=GovernanceAction.JUDGE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False


class TestDukeEarlPermissions:
    """Tests for Duke (director) and Earl (senior_manager) permissions."""

    def test_duke_can_execute(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Dukes can execute tasks."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Astaroth",
            aegis_rank="director",
            original_rank="Duke",
            branch="administrative",
            action=GovernanceAction.EXECUTE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True

    def test_duke_cannot_define_execution(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that Dukes cannot define execution (only execute)."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Astaroth",
            aegis_rank="director",
            original_rank="Duke",
            branch="administrative",
            action=GovernanceAction.DEFINE_EXECUTION,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False

    def test_earl_can_execute(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Earls can execute tasks."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Ronove",
            aegis_rank="senior_manager",
            original_rank="Earl",
            branch="administrative",
            action=GovernanceAction.EXECUTE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True


class TestMarquisPermissions:
    """Tests for Marquis (advisor) permissions.

    Per PRD §4.6: Marquis provides expert testimony.
    """

    def test_marquis_can_advise(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Marquis can provide advisories."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Amon",
            aegis_rank="advisor",
            original_rank="Marquis",
            branch="advisory",
            action=GovernanceAction.ADVISE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is True

    def test_marquis_cannot_judge(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test that Marquis cannot judge domains they advised on."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Amon",
            aegis_rank="advisor",
            original_rank="Marquis",
            branch="advisory",
            action=GovernanceAction.JUDGE,
        )
        result = enforcer.check_permission(context)
        assert result.allowed is False


class TestEnforcePermission:
    """Tests for enforce_permission which raises on violation."""

    def test_enforce_raises_on_violation(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that enforce_permission raises RankViolationError."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Paimon",
            aegis_rank="executive_director",
            original_rank="King",
            branch="legislative",
            action=GovernanceAction.DEFINE_EXECUTION,  # Prohibited for Kings
        )

        with pytest.raises(RankViolationError) as exc_info:
            enforcer.enforce_permission(context)

        assert "Paimon" in str(exc_info.value)
        assert "define_execution" in str(exc_info.value)

    def test_enforce_returns_result_on_allowed(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that enforce_permission returns result when allowed."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Paimon",
            aegis_rank="executive_director",
            original_rank="King",
            branch="legislative",
            action=GovernanceAction.INTRODUCE_MOTION,
        )

        result = enforcer.enforce_permission(context)
        assert result.allowed is True


class TestBranchConflictDetection:
    """Tests for separation of powers enforcement.

    Per PRD §2.1: No entity may define intent, execute it, AND judge it.
    """

    def test_no_conflict_on_first_action(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test no conflict when Archon hasn't acted on target yet."""
        archon_id = uuid4()
        target_id = "motion-001"

        has_conflict, reason = enforcer.check_branch_conflict(
            archon_id=archon_id,
            target_id=target_id,
            proposed_branch=GovernanceBranch.LEGISLATIVE,
        )

        assert has_conflict is False
        assert reason is None

    def test_conflict_detected_across_branches(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test conflict when same Archon acts in conflicting branches."""
        archon_id = uuid4()
        target_id = "motion-002"

        # Register action in legislative branch
        enforcer.register_action(
            archon_id=archon_id,
            target_id=target_id,
            branch=GovernanceBranch.LEGISLATIVE,
        )

        # Try to act in executive branch on same target
        has_conflict, reason = enforcer.check_branch_conflict(
            archon_id=archon_id,
            target_id=target_id,
            proposed_branch=GovernanceBranch.EXECUTIVE,
        )

        assert has_conflict is True
        assert reason is not None

    def test_witness_branch_has_no_conflicts(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that witness branch doesn't create conflicts."""
        archon_id = uuid4()
        target_id = "motion-003"

        # Register action in legislative branch
        enforcer.register_action(
            archon_id=archon_id,
            target_id=target_id,
            branch=GovernanceBranch.LEGISLATIVE,
        )

        # Witness branch should not conflict
        has_conflict, reason = enforcer.check_branch_conflict(
            archon_id=archon_id,
            target_id=target_id,
            proposed_branch=GovernanceBranch.WITNESS,
        )

        assert has_conflict is False


class TestHelperMethods:
    """Tests for helper methods.

    Per rank-matrix.yaml v2.0: Helper methods now accept original_rank
    (constitutional role) instead of aegis_rank.
    """

    def test_get_allowed_actions(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test getting allowed actions for a constitutional rank."""
        allowed = enforcer.get_allowed_actions("King")

        assert GovernanceAction.INTRODUCE_MOTION in allowed
        assert GovernanceAction.DELIBERATE in allowed
        assert GovernanceAction.RATIFY in allowed

    def test_get_prohibited_actions(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test getting prohibited actions for a constitutional rank."""
        prohibited = enforcer.get_prohibited_actions("King")

        assert GovernanceAction.DEFINE_EXECUTION in prohibited
        assert GovernanceAction.EXECUTE in prohibited
        assert GovernanceAction.JUDGE in prohibited

    def test_get_constraints(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test getting constraints for a constitutional rank."""
        constraints = enforcer.get_constraints("King")

        assert len(constraints) > 0
        assert any("WHAT" in c for c in constraints)  # Kings define WHAT, not HOW

    def test_get_branch_for_rank(self, enforcer: PermissionEnforcerAdapter) -> None:
        """Test getting branch for a constitutional rank."""
        assert enforcer.get_branch_for_rank("King") == GovernanceBranch.LEGISLATIVE
        assert enforcer.get_branch_for_rank("President") == GovernanceBranch.EXECUTIVE
        assert enforcer.get_branch_for_rank("Prince") == GovernanceBranch.JUDICIAL
        assert enforcer.get_branch_for_rank("Knight") == GovernanceBranch.WITNESS

    def test_unknown_rank_returns_none(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test unknown rank returns None for branch."""
        assert enforcer.get_branch_for_rank("unknown_rank") is None


class TestUnknownRank:
    """Tests for handling unknown constitutional ranks."""

    def test_unknown_rank_denied_with_critical_violation(
        self, enforcer: PermissionEnforcerAdapter
    ) -> None:
        """Test that unknown constitutional ranks are denied with critical violation."""
        context = PermissionContext(
            archon_id=uuid4(),
            archon_name="Unknown",
            aegis_rank="unknown_rank",
            original_rank="UnknownRank",  # This is what the lookup uses
            branch="unknown",
            action=GovernanceAction.INTRODUCE_MOTION,
        )

        result = enforcer.check_permission(context)

        assert result.allowed is False
        assert "Unknown constitutional rank" in result.violation_reason
        assert result.is_critical_violation is True
