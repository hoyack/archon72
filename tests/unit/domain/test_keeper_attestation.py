"""Unit tests for KeeperAttestation domain model (Story 5.8, AC1).

Tests the KeeperAttestation dataclass for weekly attestation tracking.

Constitutional Constraints:
- FR76: Historical attestations must be preserved (no deletion)
- FR78: Keepers SHALL attest availability weekly

Coverage:
- KeeperAttestation creation and validation
- is_valid_for_period() temporal checks
- Period calculation (7-day intervals)
- Delete prevention (FR76)
- Signature requirement
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.models.keeper_attestation import (
    ATTESTATION_PERIOD_DAYS,
    MISSED_ATTESTATIONS_THRESHOLD,
    KeeperAttestation,
    get_current_period,
)


class TestKeeperAttestationCreation:
    """Test KeeperAttestation creation and basic attributes."""

    def test_create_valid_attestation(self) -> None:
        """Test creating a valid KeeperAttestation."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=7)
        signature = b"x" * 64  # Ed25519 signature is 64 bytes

        attestation = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_end,
            signature=signature,
        )

        assert attestation.keeper_id == "KEEPER:alice"
        assert attestation.attested_at == now
        assert attestation.period_start == period_start
        assert attestation.period_end == period_end
        assert attestation.signature == signature

    def test_attestation_period_days_constant(self) -> None:
        """Test ATTESTATION_PERIOD_DAYS is 7 (weekly requirement)."""
        assert ATTESTATION_PERIOD_DAYS == 7

    def test_missed_attestations_threshold_constant(self) -> None:
        """Test MISSED_ATTESTATIONS_THRESHOLD is 2 (FR78)."""
        assert MISSED_ATTESTATIONS_THRESHOLD == 2


class TestKeeperAttestationValidation:
    """Test KeeperAttestation validation in __post_init__."""

    def test_rejects_non_uuid_id(self) -> None:
        """Test that non-UUID id is rejected."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeeperAttestation(
                id="not-a-uuid",  # type: ignore[arg-type]
                keeper_id="KEEPER:alice",
                attested_at=now,
                period_start=period_start,
                period_end=period_start + timedelta(days=7),
                signature=b"x" * 64,
            )
        assert "FR78" in str(exc_info.value)
        assert "id must be UUID" in str(exc_info.value)

    def test_rejects_empty_keeper_id(self) -> None:
        """Test that empty keeper_id is rejected."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeeperAttestation(
                id=uuid4(),
                keeper_id="",
                attested_at=now,
                period_start=period_start,
                period_end=period_start + timedelta(days=7),
                signature=b"x" * 64,
            )
        assert "FR78" in str(exc_info.value)
        assert "keeper_id must be non-empty" in str(exc_info.value)

    def test_rejects_whitespace_keeper_id(self) -> None:
        """Test that whitespace-only keeper_id is rejected."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeeperAttestation(
                id=uuid4(),
                keeper_id="   ",
                attested_at=now,
                period_start=period_start,
                period_end=period_start + timedelta(days=7),
                signature=b"x" * 64,
            )
        assert "FR78" in str(exc_info.value)
        assert "keeper_id must be non-empty" in str(exc_info.value)

    def test_rejects_non_bytes_signature(self) -> None:
        """Test that non-bytes signature is rejected."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeeperAttestation(
                id=uuid4(),
                keeper_id="KEEPER:alice",
                attested_at=now,
                period_start=period_start,
                period_end=period_start + timedelta(days=7),
                signature="not-bytes",  # type: ignore[arg-type]
            )
        assert "FR78" in str(exc_info.value)
        assert "signature must be bytes" in str(exc_info.value)

    def test_rejects_invalid_signature_length(self) -> None:
        """Test that signature with invalid length is rejected."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeeperAttestation(
                id=uuid4(),
                keeper_id="KEEPER:alice",
                attested_at=now,
                period_start=period_start,
                period_end=period_start + timedelta(days=7),
                signature=b"x" * 32,  # Ed25519 signatures are 64 bytes
            )
        assert "FR78" in str(exc_info.value)
        assert "64 bytes" in str(exc_info.value)

    def test_rejects_period_end_before_period_start(self) -> None:
        """Test that period_end before period_start is rejected."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            KeeperAttestation(
                id=uuid4(),
                keeper_id="KEEPER:alice",
                attested_at=now,
                period_start=period_start,
                period_end=period_start - timedelta(days=1),
                signature=b"x" * 64,
            )
        assert "FR78" in str(exc_info.value)
        assert "period_end must be after period_start" in str(exc_info.value)


class TestKeeperAttestationPeriodValidation:
    """Test is_valid_for_period() temporal checks."""

    def test_is_valid_for_exact_period(self) -> None:
        """Test attestation is valid for its exact period."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=7)

        attestation = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_end,
            signature=b"x" * 64,
        )

        assert attestation.is_valid_for_period(period_start, period_end) is True

    def test_is_invalid_for_different_period_start(self) -> None:
        """Test attestation is invalid for different period_start."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=7)

        attestation = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_end,
            signature=b"x" * 64,
        )

        different_start = period_start + timedelta(days=7)
        different_end = different_start + timedelta(days=7)
        assert attestation.is_valid_for_period(different_start, different_end) is False

    def test_is_invalid_for_different_period_end(self) -> None:
        """Test attestation is invalid for different period_end."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=7)

        attestation = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_end,
            signature=b"x" * 64,
        )

        # Same start but different end
        different_end = period_end + timedelta(days=1)
        assert attestation.is_valid_for_period(period_start, different_end) is False


class TestKeeperAttestationDeletePrevention:
    """Test that attestation delete is prevented (FR76)."""

    def test_delete_raises_constitutional_violation(self) -> None:
        """Test that delete() raises ConstitutionalViolationError (FR76)."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        attestation = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=b"x" * 64,
        )

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            attestation.delete()
        assert "FR80" in str(exc_info.value) or "Deletion prohibited" in str(
            exc_info.value
        )


class TestKeeperAttestationImmutability:
    """Test that attestation is immutable (frozen dataclass)."""

    def test_cannot_modify_attributes(self) -> None:
        """Test that attestation attributes cannot be modified."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        attestation = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=b"x" * 64,
        )

        with pytest.raises(AttributeError):
            attestation.keeper_id = "KEEPER:bob"  # type: ignore[misc]


class TestGetCurrentPeriod:
    """Test get_current_period() function."""

    def test_returns_7_day_period(self) -> None:
        """Test that get_current_period returns 7-day period."""
        period_start, period_end = get_current_period()

        delta = period_end - period_start
        assert delta.days == 7

    def test_period_starts_on_monday(self) -> None:
        """Test that period starts on Monday."""
        period_start, _ = get_current_period()

        # Monday is weekday 0
        assert period_start.weekday() == 0

    def test_period_starts_at_midnight_utc(self) -> None:
        """Test that period starts at midnight UTC."""
        period_start, _ = get_current_period()

        assert period_start.hour == 0
        assert period_start.minute == 0
        assert period_start.second == 0
        assert period_start.microsecond == 0
        assert period_start.tzinfo == timezone.utc

    def test_period_end_is_next_monday(self) -> None:
        """Test that period_end is the next Monday."""
        _, period_end = get_current_period()

        # Should be Monday
        assert period_end.weekday() == 0
        assert period_end.hour == 0
        assert period_end.minute == 0
        assert period_end.second == 0


class TestKeeperAttestationEquality:
    """Test KeeperAttestation equality and hashing."""

    def test_attestations_with_same_id_are_equal(self) -> None:
        """Test that two attestations with same id are equal."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        att_id = uuid4()
        signature = b"x" * 64
        created_at = now  # Use same created_at for equality check

        att1 = KeeperAttestation(
            id=att_id,
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=signature,
            created_at=created_at,
        )

        att2 = KeeperAttestation(
            id=att_id,
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=signature,
            created_at=created_at,
        )

        assert att1 == att2

    def test_attestations_with_different_id_are_not_equal(self) -> None:
        """Test that two attestations with different ids are not equal."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        signature = b"x" * 64

        att1 = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=signature,
        )

        att2 = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=signature,
        )

        assert att1 != att2

    def test_attestation_hash_based_on_id(self) -> None:
        """Test that hash is based on id."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        att_id = uuid4()

        attestation = KeeperAttestation(
            id=att_id,
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=b"x" * 64,
        )

        assert hash(attestation) == hash(att_id)
