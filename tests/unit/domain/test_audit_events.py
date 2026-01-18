"""Unit tests for audit events (Story 9.3, FR57).

Tests AuditStartedEventPayload, AuditCompletedEventPayload,
and ViolationFlaggedEventPayload for quarterly material audits.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All audit events must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.events.audit import (
    AUDIT_COMPLETED_EVENT_TYPE,
    AUDIT_STARTED_EVENT_TYPE,
    AUDIT_SYSTEM_AGENT_ID,
    MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE,
    AuditCompletedEventPayload,
    AuditStartedEventPayload,
    ViolationFlaggedEventPayload,
)


class TestAuditStartedEventPayload:
    """Tests for AuditStartedEventPayload."""

    def test_valid_payload_creation(self) -> None:
        """Test creating a valid audit started payload."""
        now = datetime.now(timezone.utc)
        payload = AuditStartedEventPayload(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            scheduled_at=now,
            started_at=now,
        )
        assert payload.audit_id == "audit-2026-Q1"
        assert payload.quarter == "2026-Q1"
        assert payload.scheduled_at == now
        assert payload.started_at == now

    def test_missing_audit_id_raises(self) -> None:
        """Test that missing audit_id raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: audit_id is required"):
            AuditStartedEventPayload(
                audit_id="",
                quarter="2026-Q1",
                scheduled_at=now,
                started_at=now,
            )

    def test_missing_quarter_raises(self) -> None:
        """Test that missing quarter raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: quarter is required"):
            AuditStartedEventPayload(
                audit_id="audit-2026-Q1",
                quarter="",
                scheduled_at=now,
                started_at=now,
            )

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        now = datetime.now(timezone.utc)
        payload = AuditStartedEventPayload(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            scheduled_at=now,
            started_at=now,
        )
        d = payload.to_dict()
        assert d["audit_id"] == "audit-2026-Q1"
        assert d["quarter"] == "2026-Q1"
        assert d["scheduled_at"] == now.isoformat()
        assert d["started_at"] == now.isoformat()

    def test_signable_content_deterministic(self) -> None:
        """Test that signable content is deterministic."""
        now = datetime.now(timezone.utc)
        payload = AuditStartedEventPayload(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            scheduled_at=now,
            started_at=now,
        )
        # Same payload should produce same bytes
        assert payload.signable_content() == payload.signable_content()

    def test_content_hash(self) -> None:
        """Test content hash generation."""
        now = datetime.now(timezone.utc)
        payload = AuditStartedEventPayload(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            scheduled_at=now,
            started_at=now,
        )
        hash_val = payload.content_hash()
        assert len(hash_val) == 64  # SHA-256 hex


class TestAuditCompletedEventPayload:
    """Tests for AuditCompletedEventPayload."""

    def test_clean_audit_creation(self) -> None:
        """Test creating a clean audit payload."""
        now = datetime.now(timezone.utc)
        payload = AuditCompletedEventPayload.clean_audit(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            materials_scanned=100,
            started_at=now,
            completed_at=now + timedelta(hours=1),
        )
        assert payload.status == "clean"
        assert payload.is_clean
        assert not payload.has_violations
        assert payload.violations_found == 0
        assert payload.remediation_deadline is None

    def test_violations_audit_creation(self) -> None:
        """Test creating a violations audit payload."""
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=7)
        payload = AuditCompletedEventPayload.violations_audit(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            materials_scanned=100,
            violations_found=5,
            started_at=now,
            completed_at=now + timedelta(hours=1),
            remediation_deadline=deadline,
        )
        assert payload.status == "violations_found"
        assert payload.has_violations
        assert not payload.is_clean
        assert payload.violations_found == 5
        assert payload.remediation_deadline == deadline

    def test_failed_audit_creation(self) -> None:
        """Test creating a failed audit payload."""
        now = datetime.now(timezone.utc)
        payload = AuditCompletedEventPayload.failed_audit(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            materials_scanned=50,
            started_at=now,
            completed_at=now + timedelta(hours=1),
        )
        assert payload.status == "failed"
        assert payload.is_failed
        assert not payload.has_violations
        assert payload.violations_found == 0

    def test_missing_audit_id_raises(self) -> None:
        """Test that missing audit_id raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: audit_id is required"):
            AuditCompletedEventPayload(
                audit_id="",
                quarter="2026-Q1",
                status="clean",
                materials_scanned=100,
                violations_found=0,
                started_at=now,
                completed_at=now,
            )

    def test_missing_quarter_raises(self) -> None:
        """Test that missing quarter raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: quarter is required"):
            AuditCompletedEventPayload(
                audit_id="audit-2026-Q1",
                quarter="",
                status="clean",
                materials_scanned=100,
                violations_found=0,
                started_at=now,
                completed_at=now,
            )

    def test_invalid_status_raises(self) -> None:
        """Test that invalid status raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: status must be"):
            AuditCompletedEventPayload(
                audit_id="audit-2026-Q1",
                quarter="2026-Q1",
                status="invalid",  # type: ignore
                materials_scanned=100,
                violations_found=0,
                started_at=now,
                completed_at=now,
            )

    def test_negative_materials_scanned_raises(self) -> None:
        """Test that negative materials_scanned raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(
            ValueError, match="FR57: materials_scanned cannot be negative"
        ):
            AuditCompletedEventPayload(
                audit_id="audit-2026-Q1",
                quarter="2026-Q1",
                status="clean",
                materials_scanned=-1,
                violations_found=0,
                started_at=now,
                completed_at=now,
            )

    def test_negative_violations_found_raises(self) -> None:
        """Test that negative violations_found raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(
            ValueError, match="FR57: violations_found cannot be negative"
        ):
            AuditCompletedEventPayload(
                audit_id="audit-2026-Q1",
                quarter="2026-Q1",
                status="clean",
                materials_scanned=100,
                violations_found=-1,
                started_at=now,
                completed_at=now,
            )

    def test_violations_found_status_requires_count(self) -> None:
        """Test that violations_found status requires violations_found > 0."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="requires violations_found > 0"):
            AuditCompletedEventPayload(
                audit_id="audit-2026-Q1",
                quarter="2026-Q1",
                status="violations_found",
                materials_scanned=100,
                violations_found=0,  # Should be > 0
                started_at=now,
                completed_at=now,
                remediation_deadline=now + timedelta(days=7),
            )

    def test_clean_status_forbids_violations(self) -> None:
        """Test that clean status cannot have violations > 0."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="clean' cannot have violations_found > 0"):
            AuditCompletedEventPayload(
                audit_id="audit-2026-Q1",
                quarter="2026-Q1",
                status="clean",
                materials_scanned=100,
                violations_found=5,  # Should be 0
                started_at=now,
                completed_at=now,
            )

    def test_violations_require_deadline(self) -> None:
        """Test that violations require remediation_deadline (AC3)."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="violations require remediation_deadline"):
            AuditCompletedEventPayload(
                audit_id="audit-2026-Q1",
                quarter="2026-Q1",
                status="violations_found",
                materials_scanned=100,
                violations_found=5,
                started_at=now,
                completed_at=now,
                remediation_deadline=None,  # Missing
            )

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=7)
        payload = AuditCompletedEventPayload.violations_audit(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            materials_scanned=100,
            violations_found=5,
            started_at=now,
            completed_at=now + timedelta(hours=1),
            remediation_deadline=deadline,
        )
        d = payload.to_dict()
        assert d["audit_id"] == "audit-2026-Q1"
        assert d["quarter"] == "2026-Q1"
        assert d["status"] == "violations_found"
        assert d["materials_scanned"] == 100
        assert d["violations_found"] == 5
        assert d["remediation_deadline"] == deadline.isoformat()

    def test_signable_content_deterministic(self) -> None:
        """Test that signable content is deterministic."""
        now = datetime.now(timezone.utc)
        payload = AuditCompletedEventPayload.clean_audit(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            materials_scanned=100,
            started_at=now,
            completed_at=now + timedelta(hours=1),
        )
        assert payload.signable_content() == payload.signable_content()

    def test_content_hash(self) -> None:
        """Test content hash generation."""
        now = datetime.now(timezone.utc)
        payload = AuditCompletedEventPayload.clean_audit(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            materials_scanned=100,
            started_at=now,
            completed_at=now + timedelta(hours=1),
        )
        hash_val = payload.content_hash()
        assert len(hash_val) == 64


class TestViolationFlaggedEventPayload:
    """Tests for ViolationFlaggedEventPayload."""

    def test_valid_payload_creation(self) -> None:
        """Test creating a valid violation flagged payload."""
        now = datetime.now(timezone.utc)
        payload = ViolationFlaggedEventPayload(
            audit_id="audit-2026-Q1",
            material_id="mat-001",
            material_type="publication",
            title="Test Publication",
            matched_terms=("sentient", "conscious"),
            flagged_at=now,
        )
        assert payload.audit_id == "audit-2026-Q1"
        assert payload.material_id == "mat-001"
        assert payload.material_type == "publication"
        assert payload.title == "Test Publication"
        assert payload.matched_terms == ("sentient", "conscious")
        assert payload.flagged_at == now
        assert payload.terms_count == 2

    def test_missing_audit_id_raises(self) -> None:
        """Test that missing audit_id raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: audit_id is required"):
            ViolationFlaggedEventPayload(
                audit_id="",
                material_id="mat-001",
                material_type="publication",
                title="Test",
                matched_terms=("sentient",),
                flagged_at=now,
            )

    def test_missing_material_id_raises(self) -> None:
        """Test that missing material_id raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: material_id is required"):
            ViolationFlaggedEventPayload(
                audit_id="audit-2026-Q1",
                material_id="",
                material_type="publication",
                title="Test",
                matched_terms=("sentient",),
                flagged_at=now,
            )

    def test_missing_material_type_raises(self) -> None:
        """Test that missing material_type raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: material_type is required"):
            ViolationFlaggedEventPayload(
                audit_id="audit-2026-Q1",
                material_id="mat-001",
                material_type="",
                title="Test",
                matched_terms=("sentient",),
                flagged_at=now,
            )

    def test_missing_title_raises(self) -> None:
        """Test that missing title raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: title is required"):
            ViolationFlaggedEventPayload(
                audit_id="audit-2026-Q1",
                material_id="mat-001",
                material_type="publication",
                title="",
                matched_terms=("sentient",),
                flagged_at=now,
            )

    def test_empty_matched_terms_raises(self) -> None:
        """Test that empty matched_terms raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR57: matched_terms is required"):
            ViolationFlaggedEventPayload(
                audit_id="audit-2026-Q1",
                material_id="mat-001",
                material_type="publication",
                title="Test",
                matched_terms=(),
                flagged_at=now,
            )

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        now = datetime.now(timezone.utc)
        payload = ViolationFlaggedEventPayload(
            audit_id="audit-2026-Q1",
            material_id="mat-001",
            material_type="publication",
            title="Test",
            matched_terms=("sentient", "conscious"),
            flagged_at=now,
        )
        d = payload.to_dict()
        assert d["audit_id"] == "audit-2026-Q1"
        assert d["material_id"] == "mat-001"
        assert d["material_type"] == "publication"
        assert d["title"] == "Test"
        assert d["matched_terms"] == ["sentient", "conscious"]
        assert d["flagged_at"] == now.isoformat()
        assert d["terms_count"] == 2

    def test_signable_content_deterministic(self) -> None:
        """Test that signable content is deterministic."""
        now = datetime.now(timezone.utc)
        payload = ViolationFlaggedEventPayload(
            audit_id="audit-2026-Q1",
            material_id="mat-001",
            material_type="publication",
            title="Test",
            matched_terms=("conscious", "sentient"),  # Different order
            flagged_at=now,
        )
        # Should sort terms for determinism
        assert payload.signable_content() == payload.signable_content()

    def test_signable_content_sorts_terms(self) -> None:
        """Test that signable content sorts matched terms for determinism."""
        now = datetime.now(timezone.utc)
        payload1 = ViolationFlaggedEventPayload(
            audit_id="audit-2026-Q1",
            material_id="mat-001",
            material_type="publication",
            title="Test",
            matched_terms=("conscious", "sentient"),
            flagged_at=now,
        )
        payload2 = ViolationFlaggedEventPayload(
            audit_id="audit-2026-Q1",
            material_id="mat-001",
            material_type="publication",
            title="Test",
            matched_terms=("sentient", "conscious"),  # Different order
            flagged_at=now,
        )
        # Should produce same signable content due to sorting
        assert payload1.signable_content() == payload2.signable_content()

    def test_content_hash(self) -> None:
        """Test content hash generation."""
        now = datetime.now(timezone.utc)
        payload = ViolationFlaggedEventPayload(
            audit_id="audit-2026-Q1",
            material_id="mat-001",
            material_type="publication",
            title="Test",
            matched_terms=("sentient",),
            flagged_at=now,
        )
        hash_val = payload.content_hash()
        assert len(hash_val) == 64


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_audit_started_event_type(self) -> None:
        """Test audit started event type constant."""
        assert AUDIT_STARTED_EVENT_TYPE == "audit.started"

    def test_audit_completed_event_type(self) -> None:
        """Test audit completed event type constant."""
        assert AUDIT_COMPLETED_EVENT_TYPE == "audit.completed"

    def test_material_violation_flagged_event_type(self) -> None:
        """Test material violation flagged event type constant."""
        assert MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE == "audit.violation.flagged"

    def test_audit_system_agent_id(self) -> None:
        """Test audit system agent ID constant."""
        assert AUDIT_SYSTEM_AGENT_ID == "system:quarterly_audit"
