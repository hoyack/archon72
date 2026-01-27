"""Tests for Epic and WorkPackage models (v2)."""


from src.domain.models.executive_planning import (
    FORBIDDEN_EXECUTIVE_FIELDS,
    SCHEMA_VERSION,
    SCHEMA_VERSION_V1,
    CapacityClaim,
    Epic,
    ExecutiveCycleResult,
    ExecutiveGates,
    GateStatus,
    PortfolioContribution,
    PortfolioIdentity,
    WorkPackage,
    validate_no_forbidden_fields,
)


class TestEpicValidation:
    """Test Epic validation rules."""

    def test_valid_epic_passes_validation(self):
        """A properly configured Epic should validate."""
        epic = Epic(
            epic_id="epic_security_001",
            intent="Establish cryptographic verification layer",
            success_signals=[
                "All vote records are cryptographically signed",
                "Tamper detection alerts within 60 seconds",
            ],
            constraints=["security", "auditability"],
            assumptions=["Key management system available"],
            discovery_required=["blocker_001"],
            mapped_motion_clauses=[
                "Section 2.1: Cryptographic proof mechanisms",
                "Section 3.4: Tamper-evident audit trail",
            ],
        )

        errors = epic.validate()
        assert errors == []

    def test_epic_requires_mapped_motion_clause(self):
        """Epic without mapped_motion_clauses should fail validation."""
        epic = Epic(
            epic_id="epic_bad_001",
            intent="Some intent",
            success_signals=["Signal 1"],
            constraints=[],
            assumptions=[],
            discovery_required=[],
            mapped_motion_clauses=[],  # Empty!
        )

        errors = epic.validate()
        assert len(errors) == 1
        assert "mapped_motion_clause" in errors[0]
        assert "traceability" in errors[0]

    def test_epic_requires_success_signal(self):
        """Epic without success_signals should fail validation."""
        epic = Epic(
            epic_id="epic_bad_002",
            intent="Some intent",
            success_signals=[],  # Empty!
            constraints=[],
            assumptions=[],
            discovery_required=[],
            mapped_motion_clauses=["Section 1"],
        )

        errors = epic.validate()
        assert len(errors) == 1
        assert "success_signal" in errors[0]
        assert "verifiability" in errors[0]

    def test_epic_missing_id_fails_validation(self):
        """Epic with empty epic_id should fail validation."""
        epic = Epic(
            epic_id="",  # Empty!
            intent="Some intent",
            success_signals=["Signal 1"],
            constraints=[],
            assumptions=[],
            discovery_required=[],
            mapped_motion_clauses=["Section 1"],
        )

        errors = epic.validate()
        assert any("epic_id" in e for e in errors)

    def test_epic_missing_intent_fails_validation(self):
        """Epic with empty intent should fail validation."""
        epic = Epic(
            epic_id="epic_001",
            intent="",  # Empty!
            success_signals=["Signal 1"],
            constraints=[],
            assumptions=[],
            discovery_required=[],
            mapped_motion_clauses=["Section 1"],
        )

        errors = epic.validate()
        assert any("intent" in e for e in errors)


class TestEpicSerialization:
    """Test Epic serialization and deserialization."""

    def test_to_dict_includes_schema_version(self):
        """Epic.to_dict should include schema_version."""
        epic = Epic(
            epic_id="epic_001",
            intent="Test intent",
            success_signals=["Signal 1"],
            constraints=["c1"],
            assumptions=["a1"],
            discovery_required=["blocker_001"],
            mapped_motion_clauses=["Section 1"],
        )

        data = epic.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION
        assert data["epic_id"] == "epic_001"
        assert data["intent"] == "Test intent"

    def test_from_dict_round_trip(self):
        """Epic should round-trip through to_dict/from_dict."""
        original = Epic(
            epic_id="epic_001",
            intent="Test intent",
            success_signals=["Signal 1", "Signal 2"],
            constraints=["c1", "c2"],
            assumptions=["a1"],
            discovery_required=["blocker_001"],
            mapped_motion_clauses=["Section 1", "Section 2"],
        )

        data = original.to_dict()
        restored = Epic.from_dict(data)

        assert restored.epic_id == original.epic_id
        assert restored.intent == original.intent
        assert restored.success_signals == original.success_signals
        assert restored.mapped_motion_clauses == original.mapped_motion_clauses


class TestWorkPackageValidation:
    """Test WorkPackage validation rules."""

    def test_valid_work_package_passes_validation(self):
        """A properly configured WorkPackage should validate."""
        wp = WorkPackage(
            package_id="wp_crypto_001",
            epic_id="epic_security_001",
            scope_description="Implement cryptographic signing for vote records",
            portfolio_id="portfolio_technical_solutions",
            dependencies=["wp_infra_001"],
            constraints_respected=["security", "auditability"],
        )

        errors = wp.validate()
        assert errors == []

    def test_work_package_requires_package_id(self):
        """WorkPackage without package_id should fail validation."""
        wp = WorkPackage(
            package_id="",  # Empty!
            epic_id="epic_001",
            scope_description="Some scope",
            portfolio_id="portfolio_tech",
        )

        errors = wp.validate()
        assert any("package_id" in e for e in errors)

    def test_work_package_requires_epic_id(self):
        """WorkPackage without epic_id should fail validation."""
        wp = WorkPackage(
            package_id="wp_001",
            epic_id="",  # Empty!
            scope_description="Some scope",
            portfolio_id="portfolio_tech",
        )

        errors = wp.validate()
        assert any("epic_id" in e for e in errors)

    def test_work_package_requires_scope_description(self):
        """WorkPackage without scope_description should fail validation."""
        wp = WorkPackage(
            package_id="wp_001",
            epic_id="epic_001",
            scope_description="",  # Empty!
            portfolio_id="portfolio_tech",
        )

        errors = wp.validate()
        assert any("scope_description" in e for e in errors)


class TestWorkPackageSerialization:
    """Test WorkPackage serialization and deserialization."""

    def test_to_dict_includes_schema_version(self):
        """WorkPackage.to_dict should include schema_version."""
        wp = WorkPackage(
            package_id="wp_001",
            epic_id="epic_001",
            scope_description="Test scope",
            portfolio_id="portfolio_tech",
        )

        data = wp.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION
        assert data["package_id"] == "wp_001"

    def test_from_dict_round_trip(self):
        """WorkPackage should round-trip through to_dict/from_dict."""
        original = WorkPackage(
            package_id="wp_001",
            epic_id="epic_001",
            scope_description="Test scope",
            portfolio_id="portfolio_tech",
            dependencies=["wp_000"],
            constraints_respected=["c1", "c2"],
        )

        data = original.to_dict()
        restored = WorkPackage.from_dict(data)

        assert restored.package_id == original.package_id
        assert restored.epic_id == original.epic_id
        assert restored.dependencies == original.dependencies


class TestForbiddenFieldsValidation:
    """Test validation of forbidden Executive fields."""

    def test_forbidden_fields_list(self):
        """FORBIDDEN_EXECUTIVE_FIELDS should contain expected fields."""
        expected = {
            "story_points",
            "estimate",
            "hours",
            "FR",
            "NFR",
            "detailed_requirements",
        }
        assert expected.issubset(FORBIDDEN_EXECUTIVE_FIELDS)

    def test_clean_dict_passes_validation(self):
        """Dict without forbidden fields should pass validation."""
        data = {
            "package_id": "wp_001",
            "scope_description": "Test scope",
            "portfolio_id": "portfolio_tech",
        }

        errors = validate_no_forbidden_fields(data, "test")
        assert errors == []

    def test_dict_with_story_points_fails_validation(self):
        """Dict with story_points should fail validation."""
        data = {
            "package_id": "wp_001",
            "scope_description": "Test scope",
            "story_points": 5,  # Forbidden!
        }

        errors = validate_no_forbidden_fields(data, "test")
        assert len(errors) == 1
        assert "story_points" in errors[0]
        assert "Administration" in errors[0]

    def test_dict_with_estimate_fails_validation(self):
        """Dict with estimate should fail validation."""
        data = {
            "task_id": "task_001",
            "title": "Test task",
            "estimate": "3 days",  # Forbidden!
        }

        errors = validate_no_forbidden_fields(data, "test")
        assert len(errors) == 1
        assert "estimate" in errors[0]

    def test_nested_forbidden_fields_detected(self):
        """Forbidden fields in nested dicts should be detected."""
        data = {
            "tasks": [
                {"task_id": "task_001", "story_points": 5},  # Forbidden!
                {"task_id": "task_002", "estimate": "2h"},  # Forbidden!
            ]
        }

        errors = validate_no_forbidden_fields(data, "contribution")
        assert len(errors) == 2
        assert any("story_points" in e for e in errors)
        assert any("estimate" in e for e in errors)

    def test_multiple_forbidden_fields_reported_together(self):
        """Multiple forbidden fields at same level should be reported together."""
        data = {
            "story_points": 5,
            "estimate": "3d",
            "hours": 24,
        }

        errors = validate_no_forbidden_fields(data, "test")
        assert len(errors) == 1
        assert "story_points" in errors[0]
        assert "estimate" in errors[0]
        assert "hours" in errors[0]


class TestPortfolioContributionV2:
    """Test PortfolioContribution with v2 work_packages."""

    def _make_portfolio(self) -> PortfolioIdentity:
        return PortfolioIdentity(
            portfolio_id="portfolio_tech",
            president_id="president_001",
            president_name="Tech President",
        )

    def _make_capacity(self) -> CapacityClaim:
        return CapacityClaim(
            claim_type="COARSE_ESTIMATE",
            units=10.0,
            unit_label="work_packages",
        )

    def test_v2_contribution_with_work_packages(self):
        """v2 contribution should use work_packages field."""
        wp = WorkPackage(
            package_id="wp_001",
            epic_id="epic_001",
            scope_description="Test scope",
            portfolio_id="portfolio_tech",
        )

        contribution = PortfolioContribution(
            cycle_id="exec_001",
            motion_id="motion_001",
            portfolio=self._make_portfolio(),
            tasks=[],
            capacity_claim=self._make_capacity(),
            work_packages=[wp],
            schema_version=SCHEMA_VERSION,
        )

        data = contribution.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION
        assert "work_packages" in data
        assert len(data["work_packages"]) == 1
        # v2 should not include tasks in output
        assert "tasks" not in data

    def test_v1_contribution_with_tasks(self):
        """v1 contribution should use tasks field."""
        contribution = PortfolioContribution(
            cycle_id="exec_001",
            motion_id="motion_001",
            portfolio=self._make_portfolio(),
            tasks=[{"task_id": "task_001", "title": "Test task"}],
            capacity_claim=self._make_capacity(),
            schema_version=SCHEMA_VERSION_V1,
        )

        data = contribution.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION_V1
        assert "tasks" in data
        assert len(data["tasks"]) == 1
        # v1 should not include work_packages in output
        assert "work_packages" not in data

    def test_v2_contribution_validates_work_packages(self):
        """v2 contribution should validate work_packages."""
        wp = WorkPackage(
            package_id="",  # Invalid!
            epic_id="epic_001",
            scope_description="Test scope",
            portfolio_id="portfolio_tech",
        )

        contribution = PortfolioContribution(
            cycle_id="exec_001",
            motion_id="motion_001",
            portfolio=self._make_portfolio(),
            tasks=[],
            capacity_claim=self._make_capacity(),
            work_packages=[wp],
            schema_version=SCHEMA_VERSION,
        )

        errors = contribution.validate()
        assert any("package_id" in e for e in errors)

    def test_v2_contribution_rejects_forbidden_fields_in_tasks(self):
        """v2 contribution should reject forbidden fields in tasks."""
        contribution = PortfolioContribution(
            cycle_id="exec_001",
            motion_id="motion_001",
            portfolio=self._make_portfolio(),
            tasks=[{"task_id": "task_001", "story_points": 5}],  # Forbidden!
            capacity_claim=self._make_capacity(),
            schema_version=SCHEMA_VERSION,
        )

        errors = contribution.validate()
        assert any("story_points" in e for e in errors)


class TestExecutiveCycleResultV2:
    """Test ExecutiveCycleResult with v2 epics."""

    def _make_portfolio(self) -> PortfolioIdentity:
        return PortfolioIdentity(
            portfolio_id="portfolio_tech",
            president_id="president_001",
            president_name="Tech President",
        )

    def _make_gates(self) -> ExecutiveGates:
        return ExecutiveGates(
            completeness=GateStatus.PASS,
            integrity=GateStatus.PASS,
            visibility=GateStatus.PASS,
        )

    def test_v2_result_includes_epics(self):
        """v2 result should include epics in output."""
        epic = Epic(
            epic_id="epic_001",
            intent="Test intent",
            success_signals=["Signal 1"],
            constraints=[],
            assumptions=[],
            discovery_required=[],
            mapped_motion_clauses=["Section 1"],
        )

        result = ExecutiveCycleResult(
            cycle_id="exec_001",
            motion_id="motion_001",
            plan_owner=self._make_portfolio(),
            contributions=[],
            attestations=[],
            blockers_requiring_escalation=[],
            execution_plan={},
            gates=self._make_gates(),
            epics=[epic],
            schema_version=SCHEMA_VERSION,
        )

        data = result.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION
        assert "epics" in data
        assert len(data["epics"]) == 1
        # v2 should not include blockers_requiring_escalation
        assert "blockers_requiring_escalation" not in data

    def test_v1_result_includes_blockers(self):
        """v1 result should include blockers_requiring_escalation."""
        result = ExecutiveCycleResult(
            cycle_id="exec_001",
            motion_id="motion_001",
            plan_owner=self._make_portfolio(),
            contributions=[],
            attestations=[],
            blockers_requiring_escalation=[],
            execution_plan={},
            gates=self._make_gates(),
            schema_version=SCHEMA_VERSION_V1,
        )

        data = result.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION_V1
        assert "blockers_requiring_escalation" in data
        # v1 should not include epics
        assert "epics" not in data

    def test_v2_result_validates_epics(self):
        """v2 result should validate epics."""
        epic = Epic(
            epic_id="epic_001",
            intent="Test intent",
            success_signals=[],  # Invalid - empty!
            constraints=[],
            assumptions=[],
            discovery_required=[],
            mapped_motion_clauses=["Section 1"],
        )

        result = ExecutiveCycleResult(
            cycle_id="exec_001",
            motion_id="motion_001",
            plan_owner=self._make_portfolio(),
            contributions=[],
            attestations=[],
            blockers_requiring_escalation=[],
            execution_plan={},
            gates=self._make_gates(),
            epics=[epic],
            schema_version=SCHEMA_VERSION,
        )

        errors = result.validate()
        assert any("success_signal" in e for e in errors)

    def test_v2_result_validates_execution_plan_forbidden_fields(self):
        """v2 result should reject forbidden fields in execution_plan."""
        result = ExecutiveCycleResult(
            cycle_id="exec_001",
            motion_id="motion_001",
            plan_owner=self._make_portfolio(),
            contributions=[],
            attestations=[],
            blockers_requiring_escalation=[],
            execution_plan={"story_points": 50},  # Forbidden!
            gates=self._make_gates(),
            schema_version=SCHEMA_VERSION,
        )

        errors = result.validate()
        assert any("story_points" in e for e in errors)
