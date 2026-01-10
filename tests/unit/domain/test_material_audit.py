"""Unit tests for material audit domain models (Story 9.3, FR57).

Tests MaterialAudit, AuditQuarter, MaterialViolation, and related
domain models for quarterly material audit tracking.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All audit events must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.models.material_audit import (
    AUDIT_ID_PREFIX,
    REMEDIATION_DEADLINE_DAYS,
    AuditQuarter,
    AuditStatus,
    MaterialAudit,
    MaterialViolation,
    RemediationStatus,
    generate_audit_id,
)


class TestAuditQuarter:
    """Tests for AuditQuarter dataclass."""

    def test_valid_quarter_creation(self) -> None:
        """Test creating valid quarters."""
        for quarter in range(1, 5):
            q = AuditQuarter(year=2026, quarter=quarter)
            assert q.year == 2026
            assert q.quarter == quarter

    def test_invalid_quarter_zero_raises(self) -> None:
        """Test that quarter 0 raises ValueError."""
        with pytest.raises(ValueError, match="FR57: quarter must be 1-4"):
            AuditQuarter(year=2026, quarter=0)

    def test_invalid_quarter_five_raises(self) -> None:
        """Test that quarter 5 raises ValueError."""
        with pytest.raises(ValueError, match="FR57: quarter must be 1-4"):
            AuditQuarter(year=2026, quarter=5)

    def test_invalid_year_raises(self) -> None:
        """Test that year before 2020 raises ValueError."""
        with pytest.raises(ValueError, match="FR57: year must be >= 2020"):
            AuditQuarter(year=2019, quarter=1)

    def test_str_format(self) -> None:
        """Test string representation format."""
        q = AuditQuarter(year=2026, quarter=3)
        assert str(q) == "2026-Q3"

    def test_from_datetime_q1(self) -> None:
        """Test creating quarter from datetime in Q1."""
        dt = datetime(2026, 2, 15, tzinfo=timezone.utc)
        q = AuditQuarter.from_datetime(dt)
        assert q.year == 2026
        assert q.quarter == 1

    def test_from_datetime_q2(self) -> None:
        """Test creating quarter from datetime in Q2."""
        dt = datetime(2026, 5, 1, tzinfo=timezone.utc)
        q = AuditQuarter.from_datetime(dt)
        assert q.year == 2026
        assert q.quarter == 2

    def test_from_datetime_q3(self) -> None:
        """Test creating quarter from datetime in Q3."""
        dt = datetime(2026, 8, 31, tzinfo=timezone.utc)
        q = AuditQuarter.from_datetime(dt)
        assert q.year == 2026
        assert q.quarter == 3

    def test_from_datetime_q4(self) -> None:
        """Test creating quarter from datetime in Q4."""
        dt = datetime(2026, 12, 31, tzinfo=timezone.utc)
        q = AuditQuarter.from_datetime(dt)
        assert q.year == 2026
        assert q.quarter == 4

    def test_next_quarter_within_year(self) -> None:
        """Test getting next quarter within same year."""
        q = AuditQuarter(year=2026, quarter=2)
        next_q = q.next_quarter()
        assert next_q.year == 2026
        assert next_q.quarter == 3

    def test_next_quarter_year_wrap(self) -> None:
        """Test getting next quarter wraps to next year from Q4."""
        q = AuditQuarter(year=2026, quarter=4)
        next_q = q.next_quarter()
        assert next_q.year == 2027
        assert next_q.quarter == 1

    def test_previous_quarter_within_year(self) -> None:
        """Test getting previous quarter within same year."""
        q = AuditQuarter(year=2026, quarter=3)
        prev_q = q.previous_quarter()
        assert prev_q.year == 2026
        assert prev_q.quarter == 2

    def test_previous_quarter_year_wrap(self) -> None:
        """Test getting previous quarter wraps to previous year from Q1."""
        q = AuditQuarter(year=2026, quarter=1)
        prev_q = q.previous_quarter()
        assert prev_q.year == 2025
        assert prev_q.quarter == 4

    def test_equality(self) -> None:
        """Test quarter equality."""
        q1 = AuditQuarter(year=2026, quarter=2)
        q2 = AuditQuarter(year=2026, quarter=2)
        q3 = AuditQuarter(year=2026, quarter=3)
        assert q1 == q2
        assert q1 != q3


class TestMaterialViolation:
    """Tests for MaterialViolation dataclass."""

    def test_valid_violation_creation(self) -> None:
        """Test creating a valid violation."""
        now = datetime.now(timezone.utc)
        v = MaterialViolation(
            material_id="mat-001",
            material_type="publication",
            title="Test Publication",
            matched_terms=("sentient", "conscious"),
            flagged_at=now,
        )
        assert v.material_id == "mat-001"
        assert v.material_type == "publication"
        assert v.title == "Test Publication"
        assert v.matched_terms == ("sentient", "conscious")
        assert v.flagged_at == now
        assert v.remediation_status == RemediationStatus.PENDING

    def test_missing_material_id_raises(self) -> None:
        """Test that missing material_id raises ValueError."""
        with pytest.raises(ValueError, match="FR57: material_id is required"):
            MaterialViolation(
                material_id="",
                material_type="publication",
                title="Test",
                matched_terms=("sentient",),
                flagged_at=datetime.now(timezone.utc),
            )

    def test_missing_material_type_raises(self) -> None:
        """Test that missing material_type raises ValueError."""
        with pytest.raises(ValueError, match="FR57: material_type is required"):
            MaterialViolation(
                material_id="mat-001",
                material_type="",
                title="Test",
                matched_terms=("sentient",),
                flagged_at=datetime.now(timezone.utc),
            )

    def test_missing_title_raises(self) -> None:
        """Test that missing title raises ValueError."""
        with pytest.raises(ValueError, match="FR57: title is required"):
            MaterialViolation(
                material_id="mat-001",
                material_type="publication",
                title="",
                matched_terms=("sentient",),
                flagged_at=datetime.now(timezone.utc),
            )

    def test_empty_matched_terms_raises(self) -> None:
        """Test that empty matched_terms raises ValueError."""
        with pytest.raises(ValueError, match="FR57: matched_terms is required"):
            MaterialViolation(
                material_id="mat-001",
                material_type="publication",
                title="Test",
                matched_terms=(),
                flagged_at=datetime.now(timezone.utc),
            )

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        now = datetime.now(timezone.utc)
        v = MaterialViolation(
            material_id="mat-001",
            material_type="publication",
            title="Test",
            matched_terms=("sentient",),
            flagged_at=now,
        )
        d = v.to_dict()
        assert d["material_id"] == "mat-001"
        assert d["material_type"] == "publication"
        assert d["title"] == "Test"
        assert d["matched_terms"] == ["sentient"]
        assert d["flagged_at"] == now.isoformat()
        assert d["remediation_status"] == "pending"

    def test_with_remediation_status(self) -> None:
        """Test creating copy with updated remediation status."""
        now = datetime.now(timezone.utc)
        v1 = MaterialViolation(
            material_id="mat-001",
            material_type="publication",
            title="Test",
            matched_terms=("sentient",),
            flagged_at=now,
        )
        v2 = v1.with_remediation_status(RemediationStatus.RESOLVED)
        assert v1.remediation_status == RemediationStatus.PENDING
        assert v2.remediation_status == RemediationStatus.RESOLVED
        assert v2.material_id == v1.material_id


class TestMaterialAudit:
    """Tests for MaterialAudit dataclass."""

    def test_create_in_progress_audit(self) -> None:
        """Test creating in-progress audit."""
        now = datetime.now(timezone.utc)
        quarter = AuditQuarter(year=2026, quarter=1)
        audit = MaterialAudit.create_in_progress(
            audit_id="audit-2026-Q1",
            quarter=quarter,
            started_at=now,
        )
        assert audit.audit_id == "audit-2026-Q1"
        assert audit.quarter == quarter
        assert audit.status == AuditStatus.IN_PROGRESS
        assert audit.materials_scanned == 0
        assert audit.violations_found == 0
        assert audit.violation_details == ()
        assert audit.started_at == now
        assert audit.completed_at is None
        assert audit.is_in_progress

    def test_missing_audit_id_raises(self) -> None:
        """Test that missing audit_id raises ValueError."""
        quarter = AuditQuarter(year=2026, quarter=1)
        with pytest.raises(ValueError, match="FR57: audit_id is required"):
            MaterialAudit(
                audit_id="",
                quarter=quarter,
                status=AuditStatus.IN_PROGRESS,
                materials_scanned=0,
                violations_found=0,
                violation_details=(),
                started_at=datetime.now(timezone.utc),
            )

    def test_invalid_audit_id_prefix_raises(self) -> None:
        """Test that invalid audit_id prefix raises ValueError."""
        quarter = AuditQuarter(year=2026, quarter=1)
        with pytest.raises(ValueError, match=f"FR57: audit_id must start with '{AUDIT_ID_PREFIX}'"):
            MaterialAudit(
                audit_id="invalid-2026-Q1",
                quarter=quarter,
                status=AuditStatus.IN_PROGRESS,
                materials_scanned=0,
                violations_found=0,
                violation_details=(),
                started_at=datetime.now(timezone.utc),
            )

    def test_violations_count_mismatch_raises(self) -> None:
        """Test that violations_found mismatch raises ValueError."""
        quarter = AuditQuarter(year=2026, quarter=1)
        with pytest.raises(ValueError, match="violations_found .* must match"):
            MaterialAudit(
                audit_id="audit-2026-Q1",
                quarter=quarter,
                status=AuditStatus.COMPLETED,
                materials_scanned=10,
                violations_found=5,  # Wrong count
                violation_details=(),  # Empty
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )

    def test_negative_materials_scanned_raises(self) -> None:
        """Test that negative materials_scanned raises ValueError."""
        quarter = AuditQuarter(year=2026, quarter=1)
        with pytest.raises(ValueError, match="FR57: materials_scanned cannot be negative"):
            MaterialAudit(
                audit_id="audit-2026-Q1",
                quarter=quarter,
                status=AuditStatus.IN_PROGRESS,
                materials_scanned=-1,
                violations_found=0,
                violation_details=(),
                started_at=datetime.now(timezone.utc),
            )

    def test_completed_without_completed_at_raises(self) -> None:
        """Test that completed status without completed_at raises ValueError."""
        quarter = AuditQuarter(year=2026, quarter=1)
        with pytest.raises(ValueError, match="completed audit must have completed_at"):
            MaterialAudit(
                audit_id="audit-2026-Q1",
                quarter=quarter,
                status=AuditStatus.COMPLETED,
                materials_scanned=10,
                violations_found=0,
                violation_details=(),
                started_at=datetime.now(timezone.utc),
                completed_at=None,  # Missing
            )

    def test_violations_without_deadline_raises(self) -> None:
        """Test that violations without remediation_deadline raises ValueError."""
        quarter = AuditQuarter(year=2026, quarter=1)
        now = datetime.now(timezone.utc)
        violation = MaterialViolation(
            material_id="mat-001",
            material_type="publication",
            title="Test",
            matched_terms=("sentient",),
            flagged_at=now,
        )
        with pytest.raises(ValueError, match="audit with violations must have remediation_deadline"):
            MaterialAudit(
                audit_id="audit-2026-Q1",
                quarter=quarter,
                status=AuditStatus.COMPLETED,
                materials_scanned=10,
                violations_found=1,
                violation_details=(violation,),
                started_at=now,
                completed_at=now,
                remediation_deadline=None,  # Missing
            )

    def test_complete_audit_clean(self) -> None:
        """Test completing audit with no violations."""
        now = datetime.now(timezone.utc)
        quarter = AuditQuarter(year=2026, quarter=1)
        audit = MaterialAudit.create_in_progress(
            audit_id="audit-2026-Q1",
            quarter=quarter,
            started_at=now,
        )
        completed = audit.complete(
            materials_scanned=100,
            violation_details=(),
            completed_at=now + timedelta(hours=1),
        )
        assert completed.is_complete
        assert completed.materials_scanned == 100
        assert completed.violations_found == 0
        assert completed.remediation_deadline is None
        assert not completed.has_violations

    def test_complete_audit_with_violations(self) -> None:
        """Test completing audit with violations."""
        now = datetime.now(timezone.utc)
        quarter = AuditQuarter(year=2026, quarter=1)
        audit = MaterialAudit.create_in_progress(
            audit_id="audit-2026-Q1",
            quarter=quarter,
            started_at=now,
        )
        violation = MaterialViolation(
            material_id="mat-001",
            material_type="publication",
            title="Test",
            matched_terms=("sentient",),
            flagged_at=now,
        )
        completed_at = now + timedelta(hours=1)
        deadline = completed_at + timedelta(days=REMEDIATION_DEADLINE_DAYS)
        completed = audit.complete(
            materials_scanned=100,
            violation_details=(violation,),
            completed_at=completed_at,
            remediation_deadline=deadline,
        )
        assert completed.is_complete
        assert completed.violations_found == 1
        assert completed.has_violations
        assert completed.remediation_deadline == deadline

    def test_fail_audit(self) -> None:
        """Test marking audit as failed."""
        now = datetime.now(timezone.utc)
        quarter = AuditQuarter(year=2026, quarter=1)
        audit = MaterialAudit.create_in_progress(
            audit_id="audit-2026-Q1",
            quarter=quarter,
            started_at=now,
        )
        failed = audit.fail(completed_at=now + timedelta(hours=1))
        assert failed.status == AuditStatus.FAILED
        assert failed.completed_at is not None

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        now = datetime.now(timezone.utc)
        quarter = AuditQuarter(year=2026, quarter=1)
        audit = MaterialAudit.create_in_progress(
            audit_id="audit-2026-Q1",
            quarter=quarter,
            started_at=now,
        )
        d = audit.to_dict()
        assert d["audit_id"] == "audit-2026-Q1"
        assert d["quarter"] == "2026-Q1"
        assert d["status"] == "in_progress"
        assert d["materials_scanned"] == 0
        assert d["violations_found"] == 0
        assert d["violation_details"] == []


class TestGenerateAuditId:
    """Tests for generate_audit_id function."""

    def test_generate_audit_id_q1(self) -> None:
        """Test generating audit ID for Q1."""
        quarter = AuditQuarter(year=2026, quarter=1)
        audit_id = generate_audit_id(quarter)
        assert audit_id == "audit-2026-Q1"

    def test_generate_audit_id_q4(self) -> None:
        """Test generating audit ID for Q4."""
        quarter = AuditQuarter(year=2025, quarter=4)
        audit_id = generate_audit_id(quarter)
        assert audit_id == "audit-2025-Q4"

    def test_generated_id_has_correct_prefix(self) -> None:
        """Test that generated ID has correct prefix."""
        quarter = AuditQuarter(year=2026, quarter=2)
        audit_id = generate_audit_id(quarter)
        assert audit_id.startswith(AUDIT_ID_PREFIX)


class TestAuditStatus:
    """Tests for AuditStatus enum."""

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert AuditStatus.SCHEDULED.value == "scheduled"
        assert AuditStatus.IN_PROGRESS.value == "in_progress"
        assert AuditStatus.COMPLETED.value == "completed"
        assert AuditStatus.FAILED.value == "failed"


class TestRemediationStatus:
    """Tests for RemediationStatus enum."""

    def test_remediation_status_values(self) -> None:
        """Test remediation status enum values."""
        assert RemediationStatus.PENDING.value == "pending"
        assert RemediationStatus.IN_PROGRESS.value == "in_progress"
        assert RemediationStatus.RESOLVED.value == "resolved"
        assert RemediationStatus.WAIVED.value == "waived"


class TestConstants:
    """Tests for module constants."""

    def test_audit_id_prefix(self) -> None:
        """Test audit ID prefix constant."""
        assert AUDIT_ID_PREFIX == "audit"

    def test_remediation_deadline_days(self) -> None:
        """Test remediation deadline constant."""
        assert REMEDIATION_DEADLINE_DAYS == 7
