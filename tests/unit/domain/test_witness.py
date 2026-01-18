"""Unit tests for Witness domain model (FR4, FR5).

Tests the Witness entity for event attestation.

Constitutional Constraints Tested:
- CT-12: Witnessing creates accountability
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.models.witness import WITNESS_PREFIX, Witness


class TestWitnessModel:
    """Tests for the Witness domain model."""

    def test_create_valid_witness(self) -> None:
        """Test creating a valid witness with proper format."""
        witness_id = f"WITNESS:{uuid4()}"
        public_key = bytes(32)  # 32 zero bytes for Ed25519
        active_from = datetime.now(timezone.utc)

        witness = Witness(
            witness_id=witness_id,
            public_key=public_key,
            active_from=active_from,
        )

        assert witness.witness_id == witness_id
        assert witness.public_key == public_key
        assert witness.active_from == active_from
        assert witness.active_until is None

    def test_witness_id_must_start_with_witness_prefix(self) -> None:
        """Test that witness_id must start with 'WITNESS:' prefix."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Witness(
                witness_id="invalid-id",
                public_key=bytes(32),
                active_from=datetime.now(timezone.utc),
            )

        assert "FR4" in str(exc_info.value)
        assert "WITNESS:" in str(exc_info.value)

    def test_witness_id_cannot_be_agent_format(self) -> None:
        """Test that witness_id cannot use agent format (SYSTEM:)."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Witness(
                witness_id="SYSTEM:watchdog",
                public_key=bytes(32),
                active_from=datetime.now(timezone.utc),
            )

        assert "FR4" in str(exc_info.value)
        assert "WITNESS:" in str(exc_info.value)

    def test_public_key_must_be_32_bytes(self) -> None:
        """Test that public_key must be exactly 32 bytes (Ed25519)."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Witness(
                witness_id=f"WITNESS:{uuid4()}",
                public_key=bytes(31),  # Wrong size
                active_from=datetime.now(timezone.utc),
            )

        assert "FR4" in str(exc_info.value)
        assert "32 bytes" in str(exc_info.value)

    def test_public_key_too_long(self) -> None:
        """Test that public_key cannot exceed 32 bytes."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Witness(
                witness_id=f"WITNESS:{uuid4()}",
                public_key=bytes(64),  # Too long
                active_from=datetime.now(timezone.utc),
            )

        assert "FR4" in str(exc_info.value)
        assert "32 bytes" in str(exc_info.value)

    def test_public_key_must_be_bytes(self) -> None:
        """Test that public_key must be bytes, not string."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Witness(
                witness_id=f"WITNESS:{uuid4()}",
                public_key="not-bytes",  # type: ignore
                active_from=datetime.now(timezone.utc),
            )

        assert "FR4" in str(exc_info.value)

    def test_witness_id_cannot_be_empty(self) -> None:
        """Test that witness_id cannot be empty string."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Witness(
                witness_id="",
                public_key=bytes(32),
                active_from=datetime.now(timezone.utc),
            )

        assert "FR4" in str(exc_info.value)

    def test_witness_is_frozen(self) -> None:
        """Test that Witness instances are immutable."""
        witness = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=bytes(32),
            active_from=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            witness.witness_id = "new-id"  # type: ignore


class TestWitnessIsActive:
    """Tests for the is_active() method."""

    def test_is_active_when_no_expiry(self) -> None:
        """Test witness is active when active_until is None."""
        witness = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=bytes(32),
            active_from=datetime.now(timezone.utc) - timedelta(hours=1),
            active_until=None,
        )

        assert witness.is_active() is True

    def test_is_active_before_active_from(self) -> None:
        """Test witness is not active before active_from."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        witness = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=bytes(32),
            active_from=future,
        )

        assert witness.is_active() is False

    def test_is_active_after_expiry(self) -> None:
        """Test witness is not active after active_until."""
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        expired = datetime.now(timezone.utc) - timedelta(hours=1)
        witness = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=bytes(32),
            active_from=past,
            active_until=expired,
        )

        assert witness.is_active() is False

    def test_is_active_at_specific_time(self) -> None:
        """Test is_active() with specific timestamp."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        witness = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=bytes(32),
            active_from=start,
            active_until=end,
        )

        # During active period
        mid = datetime(2025, 6, 15, tzinfo=timezone.utc)
        assert witness.is_active(at=mid) is True

        # Before active period
        before = datetime(2024, 12, 31, tzinfo=timezone.utc)
        assert witness.is_active(at=before) is False

        # After active period
        after = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert witness.is_active(at=after) is False


class TestWitnessHashEquality:
    """Tests for hash and equality."""

    def test_witness_equality(self) -> None:
        """Test that witnesses with same fields are equal."""
        witness_id = f"WITNESS:{uuid4()}"
        public_key = bytes(32)
        active_from = datetime.now(timezone.utc)

        witness1 = Witness(
            witness_id=witness_id,
            public_key=public_key,
            active_from=active_from,
        )
        witness2 = Witness(
            witness_id=witness_id,
            public_key=public_key,
            active_from=active_from,
        )

        assert witness1 == witness2

    def test_witness_inequality_different_id(self) -> None:
        """Test that witnesses with different IDs are not equal."""
        public_key = bytes(32)
        active_from = datetime.now(timezone.utc)

        witness1 = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=public_key,
            active_from=active_from,
        )
        witness2 = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=public_key,
            active_from=active_from,
        )

        assert witness1 != witness2

    def test_witness_hashable(self) -> None:
        """Test that witnesses can be used in sets."""
        witness = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=bytes(32),
            active_from=datetime.now(timezone.utc),
        )

        witness_set = {witness}
        assert witness in witness_set


class TestWitnessPrefix:
    """Tests for the WITNESS_PREFIX constant."""

    def test_witness_prefix_value(self) -> None:
        """Test WITNESS_PREFIX constant has correct value."""
        assert WITNESS_PREFIX == "WITNESS:"
