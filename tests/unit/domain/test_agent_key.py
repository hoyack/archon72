"""Unit tests for AgentKey domain model (FR75, FR76).

Tests the agent key registry domain model for cryptographic signing.

Constitutional Constraints:
- FR75: Key registry must track active keys
- FR76: Historical keys must be preserved (no deletion)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


class TestAgentKeyCreation:
    """Tests for AgentKey creation."""

    def test_create_with_required_fields(self) -> None:
        """AgentKey should accept all required fields."""
        from src.domain.models.agent_key import AgentKey

        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,  # Ed25519 public key is 32 bytes
            active_from=datetime.now(timezone.utc),
        )

        assert key.agent_id == "agent-001"
        assert key.key_id == "dev-abc123"
        assert len(key.public_key) == 32

    def test_active_until_is_optional(self) -> None:
        """active_until should be optional (None = currently active)."""
        from src.domain.models.agent_key import AgentKey

        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc),
            active_until=None,
        )

        assert key.active_until is None

    def test_system_agent_id_format(self) -> None:
        """System agents use SYSTEM:{service_name} format."""
        from src.domain.models.agent_key import AgentKey

        key = AgentKey(
            id=uuid4(),
            agent_id="SYSTEM:WATCHDOG",
            key_id="dev-sys123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc),
        )

        assert key.agent_id == "SYSTEM:WATCHDOG"
        assert key.is_system_agent()

    def test_user_agent_is_not_system_agent(self) -> None:
        """Regular agents are not system agents."""
        from src.domain.models.agent_key import AgentKey

        key = AgentKey(
            id=uuid4(),
            agent_id="agent-user-001",
            key_id="dev-usr123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc),
        )

        assert not key.is_system_agent()


class TestAgentKeyValidation:
    """Tests for AgentKey validation."""

    def test_empty_agent_id_raises_error(self) -> None:
        """Empty agent_id should raise validation error."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.models.agent_key import AgentKey

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            AgentKey(
                id=uuid4(),
                agent_id="",
                key_id="dev-abc123",
                public_key=b"x" * 32,
                active_from=datetime.now(timezone.utc),
            )

        assert "agent_id" in str(exc_info.value)

    def test_empty_key_id_raises_error(self) -> None:
        """Empty key_id should raise validation error."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.models.agent_key import AgentKey

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            AgentKey(
                id=uuid4(),
                agent_id="agent-001",
                key_id="",
                public_key=b"x" * 32,
                active_from=datetime.now(timezone.utc),
            )

        assert "key_id" in str(exc_info.value)

    def test_empty_public_key_raises_error(self) -> None:
        """Empty public_key should raise validation error."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.models.agent_key import AgentKey

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            AgentKey(
                id=uuid4(),
                agent_id="agent-001",
                key_id="dev-abc123",
                public_key=b"",
                active_from=datetime.now(timezone.utc),
            )

        assert "public_key" in str(exc_info.value)

    def test_wrong_length_public_key_raises_error(self) -> None:
        """Non-32-byte public_key should raise validation error (Ed25519 keys are 32 bytes)."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.models.agent_key import AgentKey

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            AgentKey(
                id=uuid4(),
                agent_id="agent-001",
                key_id="dev-abc123",
                public_key=b"x" * 16,  # Wrong length (should be 32)
                active_from=datetime.now(timezone.utc),
            )

        assert "32 bytes" in str(exc_info.value)

    def test_invalid_uuid_raises_error(self) -> None:
        """Invalid id should raise validation error."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.models.agent_key import AgentKey

        with pytest.raises(ConstitutionalViolationError):
            AgentKey(
                id="not-a-uuid",  # type: ignore
                agent_id="agent-001",
                key_id="dev-abc123",
                public_key=b"x" * 32,
                active_from=datetime.now(timezone.utc),
            )


class TestAgentKeyTemporalValidity:
    """Tests for AgentKey temporal validity."""

    def test_is_active_at_returns_true_for_active_key(self) -> None:
        """is_active_at should return True for key active at given time."""
        from src.domain.models.agent_key import AgentKey

        now = datetime.now(timezone.utc)
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=now - timedelta(hours=1),
            active_until=now + timedelta(hours=1),
        )

        assert key.is_active_at(now)

    def test_is_active_at_returns_false_for_expired_key(self) -> None:
        """is_active_at should return False for expired key."""
        from src.domain.models.agent_key import AgentKey

        now = datetime.now(timezone.utc)
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=now - timedelta(hours=2),
            active_until=now - timedelta(hours=1),
        )

        assert not key.is_active_at(now)

    def test_is_active_at_returns_false_before_active_from(self) -> None:
        """is_active_at should return False before key is active."""
        from src.domain.models.agent_key import AgentKey

        now = datetime.now(timezone.utc)
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=now + timedelta(hours=1),
            active_until=None,
        )

        assert not key.is_active_at(now)

    def test_is_active_at_returns_true_when_no_expiry(self) -> None:
        """is_active_at should return True when active_until is None."""
        from src.domain.models.agent_key import AgentKey

        now = datetime.now(timezone.utc)
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=now - timedelta(hours=1),
            active_until=None,  # No expiry
        )

        assert key.is_active_at(now)

    def test_is_currently_active(self) -> None:
        """is_currently_active should check against current time."""
        from src.domain.models.agent_key import AgentKey

        now = datetime.now(timezone.utc)
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=now - timedelta(hours=1),
            active_until=None,
        )

        assert key.is_currently_active()


class TestAgentKeyImmutability:
    """Tests for AgentKey immutability (FR76)."""

    def test_agent_key_is_frozen(self) -> None:
        """AgentKey should be immutable (frozen dataclass)."""
        from src.domain.models.agent_key import AgentKey

        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            key.agent_id = "new-agent"  # type: ignore

    def test_agent_key_delete_raises_error(self) -> None:
        """AgentKey.delete() should raise ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.models.agent_key import AgentKey

        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc),
        )

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            key.delete()

        assert "FR80" in str(exc_info.value) or "deletion" in str(exc_info.value).lower()


class TestAgentKeyHashable:
    """Tests for AgentKey hashability."""

    def test_agent_key_is_hashable(self) -> None:
        """AgentKey should be hashable (can be used in sets)."""
        from src.domain.models.agent_key import AgentKey

        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc),
        )

        # Should not raise
        key_set = {key}
        assert key in key_set

    def test_agent_keys_with_same_fields_are_equal(self) -> None:
        """AgentKeys with same fields should be equal."""
        from src.domain.models.agent_key import AgentKey

        key_id = uuid4()
        now = datetime.now(timezone.utc)
        created = datetime.now(timezone.utc)

        key1 = AgentKey(
            id=key_id,
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=now,
            created_at=created,
        )
        key2 = AgentKey(
            id=key_id,
            agent_id="agent-001",
            key_id="dev-abc123",
            public_key=b"x" * 32,
            active_from=now,
            created_at=created,
        )

        assert key1 == key2
