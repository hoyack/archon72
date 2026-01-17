"""Unit tests for contact prevention domain models.

Story: consent-gov-7.4: Follow-Up Contact Prevention

Tests:
- ContactBlockStatus has only PERMANENTLY_BLOCKED
- ContactBlock is immutable and validates permanent status
- ContactViolation always has blocked=True
- Structural prohibition: no unblock/winback methods
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.exit.contact_block_status import ContactBlockStatus
from src.domain.governance.exit.contact_block import ContactBlock
from src.domain.governance.exit.contact_violation import ContactViolation


class TestContactBlockStatus:
    """Unit tests for ContactBlockStatus enum."""

    def test_only_permanently_blocked_status_exists(self):
        """Only PERMANENTLY_BLOCKED status exists (NFR-EXIT-02)."""
        statuses = list(ContactBlockStatus)
        assert len(statuses) == 1
        assert statuses[0] == ContactBlockStatus.PERMANENTLY_BLOCKED

    def test_no_unblocked_status(self):
        """No UNBLOCKED status exists (structural prohibition)."""
        status_names = [s.name for s in ContactBlockStatus]
        assert "UNBLOCKED" not in status_names
        assert "ACTIVE" not in status_names
        assert "TEMPORARY" not in status_names

    def test_status_value_is_permanently_blocked(self):
        """Status value is descriptive."""
        assert ContactBlockStatus.PERMANENTLY_BLOCKED.value == "permanently_blocked"


class TestContactBlock:
    """Unit tests for ContactBlock domain model."""

    def test_contact_block_creation(self):
        """Can create a contact block."""
        block_id = uuid4()
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        block = ContactBlock(
            block_id=block_id,
            cluster_id=cluster_id,
            blocked_at=now,
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        assert block.block_id == block_id
        assert block.cluster_id == cluster_id
        assert block.blocked_at == now
        assert block.reason == "exit"
        assert block.status == ContactBlockStatus.PERMANENTLY_BLOCKED

    def test_contact_block_is_immutable(self):
        """ContactBlock is frozen (immutable)."""
        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=uuid4(),
            blocked_at=datetime.now(timezone.utc),
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        with pytest.raises(AttributeError):
            block.reason = "changed"  # type: ignore

    def test_contact_block_requires_permanent_status(self):
        """ContactBlock validates status is PERMANENTLY_BLOCKED."""
        # This test verifies __post_init__ validation
        # Since only PERMANENTLY_BLOCKED exists, we can't really
        # pass an invalid status. This test documents the constraint.
        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=uuid4(),
            blocked_at=datetime.now(timezone.utc),
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )
        assert block.status == ContactBlockStatus.PERMANENTLY_BLOCKED

    def test_contact_block_no_unblock_field(self):
        """ContactBlock has no unblock field (structural prohibition)."""
        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=uuid4(),
            blocked_at=datetime.now(timezone.utc),
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        assert not hasattr(block, "unblocked_at")
        assert not hasattr(block, "unblock_reason")
        assert not hasattr(block, "temporary_until")
        assert not hasattr(block, "override_by")

    def test_contact_block_equality(self):
        """ContactBlocks with same values are equal."""
        block_id = uuid4()
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        block1 = ContactBlock(
            block_id=block_id,
            cluster_id=cluster_id,
            blocked_at=now,
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        block2 = ContactBlock(
            block_id=block_id,
            cluster_id=cluster_id,
            blocked_at=now,
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        assert block1 == block2


class TestContactViolation:
    """Unit tests for ContactViolation domain model."""

    def test_contact_violation_creation(self):
        """Can create a contact violation."""
        violation_id = uuid4()
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        violation = ContactViolation(
            violation_id=violation_id,
            cluster_id=cluster_id,
            attempted_by="MessageRouter",
            attempted_at=now,
            blocked=True,
        )

        assert violation.violation_id == violation_id
        assert violation.cluster_id == cluster_id
        assert violation.attempted_by == "MessageRouter"
        assert violation.attempted_at == now
        assert violation.blocked is True

    def test_contact_violation_is_immutable(self):
        """ContactViolation is frozen (immutable)."""
        violation = ContactViolation(
            violation_id=uuid4(),
            cluster_id=uuid4(),
            attempted_by="MessageRouter",
            attempted_at=datetime.now(timezone.utc),
            blocked=True,
        )

        with pytest.raises(AttributeError):
            violation.blocked = False  # type: ignore

    def test_contact_violation_requires_blocked_true(self):
        """ContactViolation validates blocked is True."""
        with pytest.raises(ValueError) as exc_info:
            ContactViolation(
                violation_id=uuid4(),
                cluster_id=uuid4(),
                attempted_by="MessageRouter",
                attempted_at=datetime.now(timezone.utc),
                blocked=False,  # Invalid - must be True
            )

        assert "blocked must be True" in str(exc_info.value)

    def test_contact_violation_equality(self):
        """ContactViolations with same values are equal."""
        violation_id = uuid4()
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        violation1 = ContactViolation(
            violation_id=violation_id,
            cluster_id=cluster_id,
            attempted_by="MessageRouter",
            attempted_at=now,
            blocked=True,
        )

        violation2 = ContactViolation(
            violation_id=violation_id,
            cluster_id=cluster_id,
            attempted_by="MessageRouter",
            attempted_at=now,
            blocked=True,
        )

        assert violation1 == violation2

    def test_contact_violation_with_various_components(self):
        """ContactViolation can record different component names."""
        components = [
            "MessageRouter",
            "NotificationService",
            "API:/cluster/{id}/message",
            "EmailService",
            "TaskReminderService",
        ]

        for component in components:
            violation = ContactViolation(
                violation_id=uuid4(),
                cluster_id=uuid4(),
                attempted_by=component,
                attempted_at=datetime.now(timezone.utc),
                blocked=True,
            )
            assert violation.attempted_by == component


class TestStructuralProhibition:
    """Tests ensuring structural prohibition of win-back features.

    NFR-EXIT-02: No follow-up contact mechanism may exist.
    These tests verify that certain patterns DO NOT exist.
    """

    def test_no_unblock_status_in_enum(self):
        """No unblock status exists in ContactBlockStatus."""
        prohibited = [
            "UNBLOCKED",
            "ACTIVE",
            "TEMPORARY",
            "ENABLED",
            "ALLOWED",
            "REACTIVATED",
        ]

        for name in prohibited:
            assert not hasattr(ContactBlockStatus, name), (
                f"ContactBlockStatus should not have {name}"
            )

    def test_contact_block_has_no_removal_fields(self):
        """ContactBlock has no fields for block removal."""
        # Create a block and inspect its fields
        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=uuid4(),
            blocked_at=datetime.now(timezone.utc),
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        # These fields should not exist
        prohibited_fields = [
            "unblocked_at",
            "unblock_reason",
            "removed_at",
            "removed_by",
            "temporary_until",
            "override_by",
            "reactivated_at",
            "lifted_at",
        ]

        for field in prohibited_fields:
            assert not hasattr(block, field), (
                f"ContactBlock should not have field: {field}"
            )

    def test_contact_violation_always_blocked(self):
        """ContactViolation cannot be created with blocked=False."""
        # This verifies that violations cannot record successful contacts
        # to exited Clusters - contacts are ALWAYS blocked

        # Try to create with blocked=False - should fail
        with pytest.raises(ValueError):
            ContactViolation(
                violation_id=uuid4(),
                cluster_id=uuid4(),
                attempted_by="TestComponent",
                attempted_at=datetime.now(timezone.utc),
                blocked=False,
            )

        # Create with blocked=True - should succeed
        violation = ContactViolation(
            violation_id=uuid4(),
            cluster_id=uuid4(),
            attempted_by="TestComponent",
            attempted_at=datetime.now(timezone.utc),
            blocked=True,
        )
        assert violation.blocked is True
