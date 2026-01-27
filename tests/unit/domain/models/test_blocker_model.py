"""Tests for BlockerV2 model and validation rules."""

import pytest

from src.domain.models.executive_planning import (
    Blocker,
    BlockerClass,
    BlockerDisposition,
    BlockerSeverity,
    BlockerV2,
    SCHEMA_VERSION,
    SCHEMA_VERSION_V1,
    VerificationTask,
)


class TestBlockerV2Validation:
    """Test BlockerV2 validation rules."""

    def test_valid_defer_downstream_blocker(self):
        """A properly configured DEFER_DOWNSTREAM blocker should validate."""
        blocker = BlockerV2(
            id="blocker_001",
            blocker_class=BlockerClass.EXECUTION_UNCERTAINTY,
            severity=BlockerSeverity.MEDIUM,
            description="Cryptographic mechanism selection requires audit",
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

        errors = blocker.validate()
        assert errors == []

    def test_valid_escalate_now_blocker(self):
        """A properly configured ESCALATE_NOW blocker should validate."""
        blocker = BlockerV2(
            id="blocker_002",
            blocker_class=BlockerClass.INTENT_AMBIGUITY,
            severity=BlockerSeverity.HIGH,
            description="Motion scope is ambiguous",
            owner_portfolio_id="portfolio_governance",
            disposition=BlockerDisposition.ESCALATE_NOW,
            ttl="P1D",
            escalation_conditions=["Immediate Conclave review required"],
        )

        errors = blocker.validate()
        assert errors == []

    def test_valid_mitigate_blocker(self):
        """A properly configured MITIGATE_IN_EXECUTIVE blocker should validate."""
        blocker = BlockerV2(
            id="blocker_003",
            blocker_class=BlockerClass.CAPACITY_CONFLICT,
            severity=BlockerSeverity.LOW,
            description="Resource contention with parallel initiative",
            owner_portfolio_id="portfolio_resource_discovery",
            disposition=BlockerDisposition.MITIGATE_IN_EXECUTIVE,
            ttl="P3D",
            escalation_conditions=["Mitigation fails within TTL"],
            mitigation_notes="Coordinating with parallel team to sequence work",
        )

        errors = blocker.validate()
        assert errors == []

    def test_intent_ambiguity_must_escalate(self):
        """INTENT_AMBIGUITY class must have ESCALATE_NOW disposition."""
        blocker = BlockerV2(
            id="blocker_bad",
            blocker_class=BlockerClass.INTENT_AMBIGUITY,
            severity=BlockerSeverity.HIGH,
            description="Ambiguous motion",
            owner_portfolio_id="portfolio_governance",
            disposition=BlockerDisposition.DEFER_DOWNSTREAM,  # Wrong!
            ttl="P7D",
            escalation_conditions=["Some condition"],
            verification_tasks=[
                VerificationTask(
                    task_id="task_1",
                    description="Some task",
                    success_signal="Some signal",
                )
            ],
        )

        errors = blocker.validate()
        assert len(errors) == 1
        assert "INTENT_AMBIGUITY must have disposition ESCALATE_NOW" in errors[0]

    def test_defer_downstream_requires_verification_tasks(self):
        """DEFER_DOWNSTREAM disposition requires verification_tasks."""
        blocker = BlockerV2(
            id="blocker_bad",
            blocker_class=BlockerClass.EXECUTION_UNCERTAINTY,
            severity=BlockerSeverity.MEDIUM,
            description="Needs discovery",
            owner_portfolio_id="portfolio_tech",
            disposition=BlockerDisposition.DEFER_DOWNSTREAM,
            ttl="P7D",
            escalation_conditions=["Some condition"],
            verification_tasks=[],  # Empty!
        )

        errors = blocker.validate()
        assert len(errors) == 1
        assert "DEFER_DOWNSTREAM requires non-empty verification_tasks" in errors[0]

    def test_mitigate_requires_mitigation_notes(self):
        """MITIGATE_IN_EXECUTIVE disposition requires mitigation_notes."""
        blocker = BlockerV2(
            id="blocker_bad",
            blocker_class=BlockerClass.CAPACITY_CONFLICT,
            severity=BlockerSeverity.LOW,
            description="Resource issue",
            owner_portfolio_id="portfolio_resource",
            disposition=BlockerDisposition.MITIGATE_IN_EXECUTIVE,
            ttl="P3D",
            escalation_conditions=["Some condition"],
            mitigation_notes=None,  # Missing!
        )

        errors = blocker.validate()
        assert len(errors) == 1
        assert "MITIGATE_IN_EXECUTIVE requires mitigation_notes" in errors[0]

    def test_missing_required_fields(self):
        """Blocker with missing required fields should fail validation."""
        blocker = BlockerV2(
            id="",  # Empty!
            blocker_class=BlockerClass.EXECUTION_UNCERTAINTY,
            severity=BlockerSeverity.MEDIUM,
            description="",  # Empty!
            owner_portfolio_id="",  # Empty!
            disposition=BlockerDisposition.ESCALATE_NOW,
            ttl="",  # Empty!
            escalation_conditions=[],  # Empty!
        )

        errors = blocker.validate()
        assert len(errors) == 5
        assert any("id" in e for e in errors)
        assert any("description" in e for e in errors)
        assert any("owner_portfolio_id" in e for e in errors)
        assert any("ttl" in e for e in errors)
        assert any("escalation_conditions" in e for e in errors)


class TestBlockerV2Serialization:
    """Test BlockerV2 serialization and deserialization."""

    def test_to_dict_includes_schema_version(self):
        """to_dict should include schema_version."""
        blocker = BlockerV2(
            id="blocker_001",
            blocker_class=BlockerClass.EXECUTION_UNCERTAINTY,
            severity=BlockerSeverity.MEDIUM,
            description="Test blocker",
            owner_portfolio_id="portfolio_tech",
            disposition=BlockerDisposition.ESCALATE_NOW,
            ttl="P7D",
            escalation_conditions=["Condition 1"],
        )

        data = blocker.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION
        assert data["blocker_class"] == "EXECUTION_UNCERTAINTY"
        assert data["disposition"] == "ESCALATE_NOW"

    def test_from_dict_round_trip(self):
        """BlockerV2 should round-trip through to_dict/from_dict."""
        original = BlockerV2(
            id="blocker_001",
            blocker_class=BlockerClass.EXECUTION_UNCERTAINTY,
            severity=BlockerSeverity.HIGH,
            description="Test blocker",
            owner_portfolio_id="portfolio_tech",
            disposition=BlockerDisposition.DEFER_DOWNSTREAM,
            ttl="P7D",
            escalation_conditions=["Condition 1", "Condition 2"],
            verification_tasks=[
                VerificationTask(
                    task_id="task_1",
                    description="Do the thing",
                    success_signal="Thing done",
                )
            ],
            mitigation_notes=None,
        )

        data = original.to_dict()
        restored = BlockerV2.from_dict(data)

        assert restored.id == original.id
        assert restored.blocker_class == original.blocker_class
        assert restored.severity == original.severity
        assert restored.disposition == original.disposition
        assert len(restored.verification_tasks) == 1
        assert restored.verification_tasks[0].task_id == "task_1"


class TestBlockerV1Compatibility:
    """Test v1 Blocker backward compatibility."""

    def test_v1_blocker_to_dict_includes_version(self):
        """v1 Blocker should include schema_version in to_dict."""
        blocker = Blocker(
            severity="MEDIUM",
            description="Legacy blocker",
            requires_escalation=False,
        )

        data = blocker.to_dict()
        assert data["schema_version"] == SCHEMA_VERSION_V1
        assert data["requires_escalation"] is False

    def test_v1_to_v2_conversion_escalation(self):
        """v1 blocker with requires_escalation=True should convert to ESCALATE_NOW."""
        v1_blocker = Blocker(
            severity="HIGH",
            description="Needs escalation",
            requires_escalation=True,
        )

        v2_blocker = v1_blocker.to_v2(
            blocker_id="converted_001",
            owner_portfolio_id="portfolio_tech",
        )

        assert v2_blocker.blocker_class == BlockerClass.INTENT_AMBIGUITY
        assert v2_blocker.disposition == BlockerDisposition.ESCALATE_NOW
        assert v2_blocker.severity == BlockerSeverity.HIGH

    def test_v1_to_v2_conversion_no_escalation(self):
        """v1 blocker with requires_escalation=False should convert to DEFER_DOWNSTREAM."""
        v1_blocker = Blocker(
            severity="MEDIUM",
            description="Regular blocker",
            requires_escalation=False,
        )

        v2_blocker = v1_blocker.to_v2(
            blocker_id="converted_002",
            owner_portfolio_id="portfolio_tech",
        )

        assert v2_blocker.blocker_class == BlockerClass.EXECUTION_UNCERTAINTY
        assert v2_blocker.disposition == BlockerDisposition.DEFER_DOWNSTREAM
        assert v2_blocker.ttl == "P7D"  # Default TTL


class TestVerificationTask:
    """Test VerificationTask model."""

    def test_to_dict(self):
        """VerificationTask should serialize correctly."""
        task = VerificationTask(
            task_id="discovery_001",
            description="Conduct security audit",
            success_signal="Audit report with recommendation",
        )

        data = task.to_dict()
        assert data["task_id"] == "discovery_001"
        assert data["description"] == "Conduct security audit"
        assert data["success_signal"] == "Audit report with recommendation"
