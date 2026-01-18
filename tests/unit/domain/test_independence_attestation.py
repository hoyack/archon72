"""Unit tests for Independence Attestation domain model (FR98, FR133).

Tests the IndependenceAttestation, ConflictDeclaration, and DeclarationType
domain models for annual Keeper independence attestation tracking.

Constitutional Constraints Tested:
- FR133: Annual independence attestation requirement
- FR76: Delete prevention for audit trail preservation
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError


class TestDeclarationType:
    """Tests for DeclarationType enum."""

    def test_financial_type_exists(self) -> None:
        """Test FINANCIAL declaration type is available."""
        from src.domain.models.independence_attestation import DeclarationType

        assert DeclarationType.FINANCIAL.value == "FINANCIAL"

    def test_organizational_type_exists(self) -> None:
        """Test ORGANIZATIONAL declaration type is available."""
        from src.domain.models.independence_attestation import DeclarationType

        assert DeclarationType.ORGANIZATIONAL.value == "ORGANIZATIONAL"

    def test_personal_type_exists(self) -> None:
        """Test PERSONAL declaration type is available."""
        from src.domain.models.independence_attestation import DeclarationType

        assert DeclarationType.PERSONAL.value == "PERSONAL"

    def test_none_declared_type_exists(self) -> None:
        """Test NONE_DECLARED declaration type is available."""
        from src.domain.models.independence_attestation import DeclarationType

        assert DeclarationType.NONE_DECLARED.value == "NONE_DECLARED"


class TestConflictDeclaration:
    """Tests for ConflictDeclaration frozen dataclass."""

    def test_creation_with_valid_fields(self) -> None:
        """Test ConflictDeclaration creates with all required fields."""
        from src.domain.models.independence_attestation import (
            ConflictDeclaration,
            DeclarationType,
        )

        now = datetime.now(timezone.utc)
        declaration = ConflictDeclaration(
            declaration_type=DeclarationType.FINANCIAL,
            description="Investment in competing AI governance platform",
            related_party="Acme AI Corp",
            disclosed_at=now,
        )

        assert declaration.declaration_type == DeclarationType.FINANCIAL
        assert (
            declaration.description == "Investment in competing AI governance platform"
        )
        assert declaration.related_party == "Acme AI Corp"
        assert declaration.disclosed_at == now

    def test_frozen_immutable(self) -> None:
        """Test ConflictDeclaration is immutable (frozen)."""
        from src.domain.models.independence_attestation import (
            ConflictDeclaration,
            DeclarationType,
        )

        declaration = ConflictDeclaration(
            declaration_type=DeclarationType.PERSONAL,
            description="Family member works at AI lab",
            related_party="Jane Doe",
            disclosed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            declaration.description = "Changed"  # type: ignore[misc]

    def test_hashable_for_set_operations(self) -> None:
        """Test ConflictDeclaration is hashable for set comparisons."""
        from src.domain.models.independence_attestation import (
            ConflictDeclaration,
            DeclarationType,
        )

        now = datetime.now(timezone.utc)
        declaration1 = ConflictDeclaration(
            declaration_type=DeclarationType.FINANCIAL,
            description="Same conflict",
            related_party="Same party",
            disclosed_at=now,
        )
        declaration2 = ConflictDeclaration(
            declaration_type=DeclarationType.FINANCIAL,
            description="Same conflict",
            related_party="Same party",
            disclosed_at=now,
        )

        # Should be hashable and equal
        assert hash(declaration1) == hash(declaration2)
        assert declaration1 == declaration2

        # Should work in sets
        conflict_set = {declaration1, declaration2}
        assert len(conflict_set) == 1


class TestIndependenceAttestation:
    """Tests for IndependenceAttestation frozen dataclass."""

    def _create_valid_attestation(
        self,
        keeper_id: str = "KEEPER:alice",
        attestation_year: int = 2026,
        conflicts: list | None = None,
        organizations: list | None = None,
    ) -> IndependenceAttestation:
        """Helper to create a valid attestation for testing."""
        from src.domain.models.independence_attestation import IndependenceAttestation

        return IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=datetime.now(timezone.utc),
            attestation_year=attestation_year,
            conflict_declarations=conflicts or [],
            affiliated_organizations=organizations or [],
            signature=b"x" * 64,  # Ed25519 signature placeholder
        )

    def test_creation_with_all_required_fields(self) -> None:
        """Test IndependenceAttestation creates with all required fields."""
        from src.domain.models.independence_attestation import (
            ConflictDeclaration,
            DeclarationType,
            IndependenceAttestation,
        )

        att_id = uuid4()
        now = datetime.now(timezone.utc)
        conflict = ConflictDeclaration(
            declaration_type=DeclarationType.ORGANIZATIONAL,
            description="Board member of AI Ethics Foundation",
            related_party="AI Ethics Foundation",
            disclosed_at=now,
        )

        attestation = IndependenceAttestation(
            id=att_id,
            keeper_id="KEEPER:bob",
            attested_at=now,
            attestation_year=2026,
            conflict_declarations=[conflict],
            affiliated_organizations=["AI Safety Institute", "OpenAI"],
            signature=b"s" * 64,
        )

        assert attestation.id == att_id
        assert attestation.keeper_id == "KEEPER:bob"
        assert attestation.attested_at == now
        assert attestation.attestation_year == 2026
        assert len(attestation.conflict_declarations) == 1
        assert attestation.conflict_declarations[0] == conflict
        assert attestation.affiliated_organizations == ["AI Safety Institute", "OpenAI"]
        assert len(attestation.signature) == 64

    def test_frozen_immutable(self) -> None:
        """Test IndependenceAttestation is immutable (frozen)."""
        attestation = self._create_valid_attestation()

        with pytest.raises(AttributeError):
            attestation.keeper_id = "KEEPER:changed"  # type: ignore[misc]

    def test_validation_rejects_invalid_id(self) -> None:
        """Test validation rejects non-UUID id."""
        from src.domain.models.independence_attestation import IndependenceAttestation

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            IndependenceAttestation(
                id="not-a-uuid",  # type: ignore[arg-type]
                keeper_id="KEEPER:alice",
                attested_at=datetime.now(timezone.utc),
                attestation_year=2026,
                conflict_declarations=[],
                affiliated_organizations=[],
                signature=b"x" * 64,
            )

        assert "FR133" in str(exc_info.value)
        assert "id must be UUID" in str(exc_info.value)

    def test_validation_rejects_empty_keeper_id(self) -> None:
        """Test validation rejects empty keeper_id."""
        from src.domain.models.independence_attestation import IndependenceAttestation

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            IndependenceAttestation(
                id=uuid4(),
                keeper_id="",
                attested_at=datetime.now(timezone.utc),
                attestation_year=2026,
                conflict_declarations=[],
                affiliated_organizations=[],
                signature=b"x" * 64,
            )

        assert "FR133" in str(exc_info.value)
        assert "keeper_id must be non-empty" in str(exc_info.value)

    def test_validation_rejects_invalid_signature_length(self) -> None:
        """Test validation rejects signature not 64 bytes."""
        from src.domain.models.independence_attestation import IndependenceAttestation

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            IndependenceAttestation(
                id=uuid4(),
                keeper_id="KEEPER:alice",
                attested_at=datetime.now(timezone.utc),
                attestation_year=2026,
                conflict_declarations=[],
                affiliated_organizations=[],
                signature=b"short",
            )

        assert "FR133" in str(exc_info.value)
        assert "signature must be 64 bytes" in str(exc_info.value)

    def test_validation_rejects_non_bytes_signature(self) -> None:
        """Test validation rejects non-bytes signature."""
        from src.domain.models.independence_attestation import IndependenceAttestation

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            IndependenceAttestation(
                id=uuid4(),
                keeper_id="KEEPER:alice",
                attested_at=datetime.now(timezone.utc),
                attestation_year=2026,
                conflict_declarations=[],
                affiliated_organizations=[],
                signature="not-bytes",  # type: ignore[arg-type]
            )

        assert "FR133" in str(exc_info.value)
        assert "signature must be bytes" in str(exc_info.value)

    def test_is_valid_for_year_returns_true_for_matching_year(self) -> None:
        """Test is_valid_for_year returns True for matching year."""
        attestation = self._create_valid_attestation(attestation_year=2026)

        assert attestation.is_valid_for_year(2026) is True

    def test_is_valid_for_year_returns_false_for_different_year(self) -> None:
        """Test is_valid_for_year returns False for different year."""
        attestation = self._create_valid_attestation(attestation_year=2025)

        assert attestation.is_valid_for_year(2026) is False

    def test_delete_prevention_mixin_applied(self) -> None:
        """Test delete prevention is enforced (FR80 via DeletePreventionMixin)."""
        attestation = self._create_valid_attestation()

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            attestation.delete()  # type: ignore[attr-defined]

        # DeletePreventionMixin uses FR80 reference
        assert "FR80" in str(exc_info.value) or "Deletion prohibited" in str(
            exc_info.value
        )

    def test_hash_based_on_id(self) -> None:
        """Test hash is based on id for set membership."""
        from src.domain.models.independence_attestation import IndependenceAttestation

        shared_id = uuid4()
        attestation1 = IndependenceAttestation(
            id=shared_id,
            keeper_id="KEEPER:alice",
            attested_at=datetime.now(timezone.utc),
            attestation_year=2026,
            conflict_declarations=[],
            affiliated_organizations=["Org1"],
            signature=b"a" * 64,
        )
        attestation2 = IndependenceAttestation(
            id=shared_id,
            keeper_id="KEEPER:alice",
            attested_at=datetime.now(timezone.utc),
            attestation_year=2026,
            conflict_declarations=[],
            affiliated_organizations=["Org2"],  # Different orgs
            signature=b"b" * 64,  # Different signature
        )

        # Same id means same hash
        assert hash(attestation1) == hash(attestation2)

    def test_created_at_default_timestamp(self) -> None:
        """Test created_at defaults to current time."""
        before = datetime.now(timezone.utc)
        attestation = self._create_valid_attestation()
        after = datetime.now(timezone.utc)

        assert before <= attestation.created_at <= after


class TestAttestationConstants:
    """Tests for attestation-related constants."""

    def test_attestation_deadline_days(self) -> None:
        """Test ATTESTATION_DEADLINE_DAYS is 365 (annual)."""
        from src.domain.models.independence_attestation import ATTESTATION_DEADLINE_DAYS

        assert ATTESTATION_DEADLINE_DAYS == 365

    def test_deadline_grace_period_days(self) -> None:
        """Test DEADLINE_GRACE_PERIOD_DAYS is 30."""
        from src.domain.models.independence_attestation import (
            DEADLINE_GRACE_PERIOD_DAYS,
        )

        assert DEADLINE_GRACE_PERIOD_DAYS == 30


class TestGetCurrentAttestationYear:
    """Tests for get_current_attestation_year function."""

    def test_returns_current_year(self) -> None:
        """Test function returns current calendar year."""
        from src.domain.models.independence_attestation import (
            get_current_attestation_year,
        )

        expected_year = datetime.now(timezone.utc).year
        assert get_current_attestation_year() == expected_year


class TestCalculateDeadline:
    """Tests for calculate_deadline function."""

    def test_deadline_is_anniversary_plus_grace_period(self) -> None:
        """Test deadline is anniversary of first attestation + grace period."""
        from src.domain.models.independence_attestation import (
            DEADLINE_GRACE_PERIOD_DAYS,
            calculate_deadline,
        )

        # First attestation on Jan 15, 2025
        first_attestation = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        # Current year is 2026
        deadline = calculate_deadline(first_attestation, current_year=2026)

        # Expected: Jan 15, 2026 + 30 days grace = Feb 14, 2026
        expected = datetime(2026, 1, 15, tzinfo=timezone.utc) + timedelta(
            days=DEADLINE_GRACE_PERIOD_DAYS
        )
        assert deadline.date() == expected.date()

    def test_deadline_immediate_for_no_previous_attestation(self) -> None:
        """Test deadline is immediate if no previous attestation."""
        from src.domain.models.independence_attestation import calculate_deadline

        before = datetime.now(timezone.utc)
        deadline = calculate_deadline(None, current_year=2026)
        after = datetime.now(timezone.utc)

        # Should be essentially now (immediate)
        assert before <= deadline <= after
