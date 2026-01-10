"""Unit tests for KeeperKey domain model (FR68, FR76).

Tests the KeeperKey entity for Keeper signature operations.
Validates temporal validity, validation, and delete prevention.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError


class TestKeeperKeyCreation:
    """Test KeeperKey creation with valid fields."""

    def test_create_keeper_key_with_valid_fields(self) -> None:
        """KeeperKey can be created with all valid fields."""
        from src.domain.models.keeper_key import KeeperKey

        key_id = uuid4()
        keeper_id = "KEEPER:alice"
        hsm_key_id = "keeper-key-001"
        public_key = b"x" * 32  # Ed25519 public key is 32 bytes
        active_from = datetime.now(timezone.utc)

        keeper_key = KeeperKey(
            id=key_id,
            keeper_id=keeper_id,
            key_id=hsm_key_id,
            public_key=public_key,
            active_from=active_from,
        )

        assert keeper_key.id == key_id
        assert keeper_key.keeper_id == keeper_id
        assert keeper_key.key_id == hsm_key_id
        assert keeper_key.public_key == public_key
        assert keeper_key.active_from == active_from
        assert keeper_key.active_until is None

    def test_create_keeper_key_with_expiry(self) -> None:
        """KeeperKey can be created with active_until set."""
        from src.domain.models.keeper_key import KeeperKey

        active_from = datetime.now(timezone.utc) - timedelta(days=30)
        active_until = datetime.now(timezone.utc)

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:bob",
            key_id="keeper-key-002",
            public_key=b"y" * 32,
            active_from=active_from,
            active_until=active_until,
        )

        assert keeper_key.active_until == active_until

    def test_keeper_key_is_frozen(self) -> None:
        """KeeperKey is immutable (frozen dataclass)."""
        from src.domain.models.keeper_key import KeeperKey

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:charlie",
            key_id="keeper-key-003",
            public_key=b"z" * 32,
            active_from=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            keeper_key.keeper_id = "KEEPER:new"  # type: ignore[misc]


class TestKeeperKeyTemporalValidity:
    """Test is_active_at() temporal validity checks."""

    def test_is_active_at_returns_true_for_active_key(self) -> None:
        """Key is active when timestamp is within validity period."""
        from src.domain.models.keeper_key import KeeperKey

        active_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
        active_until = datetime(2025, 12, 31, tzinfo=timezone.utc)

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"a" * 32,
            active_from=active_from,
            active_until=active_until,
        )

        check_time = datetime(2025, 6, 15, tzinfo=timezone.utc)
        assert keeper_key.is_active_at(check_time) is True

    def test_is_active_at_returns_false_before_active_from(self) -> None:
        """Key is not active before active_from."""
        from src.domain.models.keeper_key import KeeperKey

        active_from = datetime(2025, 6, 1, tzinfo=timezone.utc)

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"b" * 32,
            active_from=active_from,
        )

        check_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        assert keeper_key.is_active_at(check_time) is False

    def test_is_active_at_returns_false_after_active_until(self) -> None:
        """Key is not active after active_until."""
        from src.domain.models.keeper_key import KeeperKey

        active_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
        active_until = datetime(2025, 6, 1, tzinfo=timezone.utc)

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"c" * 32,
            active_from=active_from,
            active_until=active_until,
        )

        check_time = datetime(2025, 12, 1, tzinfo=timezone.utc)
        assert keeper_key.is_active_at(check_time) is False

    def test_is_active_at_returns_true_when_no_expiry(self) -> None:
        """Key with no active_until is active indefinitely after active_from."""
        from src.domain.models.keeper_key import KeeperKey

        active_from = datetime(2025, 1, 1, tzinfo=timezone.utc)

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"d" * 32,
            active_from=active_from,
            active_until=None,
        )

        # Far future date
        check_time = datetime(2030, 12, 31, tzinfo=timezone.utc)
        assert keeper_key.is_active_at(check_time) is True


class TestKeeperKeyIsCurrentlyActive:
    """Test is_currently_active() convenience method."""

    def test_is_currently_active_returns_true_for_active_key(self) -> None:
        """Key is currently active when no expiry and active_from is past."""
        from src.domain.models.keeper_key import KeeperKey

        active_from = datetime.now(timezone.utc) - timedelta(days=1)

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"e" * 32,
            active_from=active_from,
        )

        assert keeper_key.is_currently_active() is True

    def test_is_currently_active_returns_false_for_expired_key(self) -> None:
        """Key is not currently active when expired."""
        from src.domain.models.keeper_key import KeeperKey

        active_from = datetime.now(timezone.utc) - timedelta(days=30)
        active_until = datetime.now(timezone.utc) - timedelta(days=1)

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"f" * 32,
            active_from=active_from,
            active_until=active_until,
        )

        assert keeper_key.is_currently_active() is False

    def test_is_currently_active_returns_false_for_future_key(self) -> None:
        """Key is not currently active when active_from is in future."""
        from src.domain.models.keeper_key import KeeperKey

        active_from = datetime.now(timezone.utc) + timedelta(days=1)

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"g" * 32,
            active_from=active_from,
        )

        assert keeper_key.is_currently_active() is False


class TestKeeperKeyValidation:
    """Test validation errors for invalid fields."""

    def test_invalid_id_raises_constitutional_violation(self) -> None:
        """Non-UUID id raises ConstitutionalViolationError."""
        from src.domain.models.keeper_key import KeeperKey

        with pytest.raises(ConstitutionalViolationError, match="FR68.*id must be UUID"):
            KeeperKey(
                id="not-a-uuid",  # type: ignore[arg-type]
                keeper_id="KEEPER:test",
                key_id="test-key",
                public_key=b"h" * 32,
                active_from=datetime.now(timezone.utc),
            )

    def test_empty_keeper_id_raises_constitutional_violation(self) -> None:
        """Empty keeper_id raises ConstitutionalViolationError."""
        from src.domain.models.keeper_key import KeeperKey

        with pytest.raises(
            ConstitutionalViolationError, match="FR68.*keeper_id must be non-empty"
        ):
            KeeperKey(
                id=uuid4(),
                keeper_id="",
                key_id="test-key",
                public_key=b"i" * 32,
                active_from=datetime.now(timezone.utc),
            )

    def test_whitespace_keeper_id_raises_constitutional_violation(self) -> None:
        """Whitespace-only keeper_id raises ConstitutionalViolationError."""
        from src.domain.models.keeper_key import KeeperKey

        with pytest.raises(
            ConstitutionalViolationError, match="FR68.*keeper_id must be non-empty"
        ):
            KeeperKey(
                id=uuid4(),
                keeper_id="   ",
                key_id="test-key",
                public_key=b"j" * 32,
                active_from=datetime.now(timezone.utc),
            )

    def test_empty_key_id_raises_constitutional_violation(self) -> None:
        """Empty key_id raises ConstitutionalViolationError."""
        from src.domain.models.keeper_key import KeeperKey

        with pytest.raises(
            ConstitutionalViolationError, match="FR68.*key_id must be non-empty"
        ):
            KeeperKey(
                id=uuid4(),
                keeper_id="KEEPER:test",
                key_id="",
                public_key=b"k" * 32,
                active_from=datetime.now(timezone.utc),
            )

    def test_invalid_public_key_length_raises_constitutional_violation(self) -> None:
        """Non-32-byte public_key raises ConstitutionalViolationError."""
        from src.domain.models.keeper_key import KeeperKey

        with pytest.raises(
            ConstitutionalViolationError, match="FR68.*public_key must be 32 bytes"
        ):
            KeeperKey(
                id=uuid4(),
                keeper_id="KEEPER:test",
                key_id="test-key",
                public_key=b"short",  # Not 32 bytes
                active_from=datetime.now(timezone.utc),
            )

    def test_non_bytes_public_key_raises_constitutional_violation(self) -> None:
        """Non-bytes public_key raises ConstitutionalViolationError."""
        from src.domain.models.keeper_key import KeeperKey

        with pytest.raises(
            ConstitutionalViolationError, match="FR68.*public_key must be bytes"
        ):
            KeeperKey(
                id=uuid4(),
                keeper_id="KEEPER:test",
                key_id="test-key",
                public_key="not bytes",  # type: ignore[arg-type]
                active_from=datetime.now(timezone.utc),
            )


class TestKeeperKeyDeletePrevention:
    """Test delete prevention (FR76)."""

    def test_delete_raises_constitutional_violation(self) -> None:
        """Calling delete() raises ConstitutionalViolationError (FR80 from mixin)."""
        from src.domain.models.keeper_key import KeeperKey

        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"l" * 32,
            active_from=datetime.now(timezone.utc),
        )

        # FR80 is the general deletion prohibition from DeletePreventionMixin
        with pytest.raises(
            ConstitutionalViolationError, match="FR80.*[Dd]eletion.*prohibited"
        ):
            keeper_key.delete()


class TestKeeperKeyHashEquality:
    """Test hash and equality behavior."""

    def test_keeper_keys_with_same_fields_are_equal(self) -> None:
        """KeeperKeys with identical fields are equal (frozen dataclass)."""
        from src.domain.models.keeper_key import KeeperKey

        key_id = uuid4()
        now = datetime.now(timezone.utc)
        created = datetime(2025, 1, 1, tzinfo=timezone.utc)

        key1 = KeeperKey(
            id=key_id,
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"m" * 32,
            active_from=now,
            created_at=created,  # Explicit to ensure equality
        )

        key2 = KeeperKey(
            id=key_id,
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"m" * 32,
            active_from=now,
            created_at=created,  # Same created_at
        )

        assert key1 == key2

    def test_keeper_key_can_be_used_in_set(self) -> None:
        """KeeperKey can be added to a set."""
        from src.domain.models.keeper_key import KeeperKey

        key_id = uuid4()

        keeper_key = KeeperKey(
            id=key_id,
            keeper_id="KEEPER:test",
            key_id="test-key",
            public_key=b"n" * 32,
            active_from=datetime.now(timezone.utc),
        )

        key_set: set[KeeperKey] = {keeper_key}
        assert keeper_key in key_set


class TestKeeperKeyPrefix:
    """Test KEEPER_ID_PREFIX constant."""

    def test_keeper_id_prefix_constant_exists(self) -> None:
        """KEEPER_ID_PREFIX constant is exported."""
        from src.domain.models.keeper_key import KEEPER_ID_PREFIX

        assert KEEPER_ID_PREFIX == "KEEPER:"
