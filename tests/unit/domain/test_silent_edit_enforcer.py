"""Unit tests for SilentEditEnforcer domain service (Story 2.5, FR13).

Tests the domain service that enforces the No Silent Edits constraint
by verifying content hashes before publish operations.

Constitutional Constraints Verified:
- FR13: Published hash must equal canonical hash
- CT-11: Silent failure destroys legitimacy → Violations raise errors
- CT-13: Integrity outranks availability → Block publish on mismatch
"""

from uuid import uuid4

import pytest

from src.domain.errors.silent_edit import FR13ViolationError
from src.domain.services.silent_edit_enforcer import SilentEditEnforcer


class TestSilentEditEnforcer:
    """Test suite for SilentEditEnforcer domain service."""

    @pytest.fixture
    def enforcer(self) -> SilentEditEnforcer:
        """Create a fresh SilentEditEnforcer instance."""
        return SilentEditEnforcer()

    def test_register_content_hash(self, enforcer: SilentEditEnforcer) -> None:
        """Content hash can be registered for a content ID."""
        content_id = uuid4()
        content_hash = "a" * 64  # SHA-256 length

        enforcer.register_hash(content_id, content_hash)

        assert enforcer.get_stored_hash(content_id) == content_hash

    def test_get_stored_hash_returns_none_for_unknown(
        self, enforcer: SilentEditEnforcer
    ) -> None:
        """Getting hash for unknown content returns None."""
        unknown_id = uuid4()
        assert enforcer.get_stored_hash(unknown_id) is None

    def test_verify_matching_hashes_returns_true(
        self, enforcer: SilentEditEnforcer
    ) -> None:
        """Verify returns True when hashes match (AC1)."""
        content_id = uuid4()
        content_hash = "b" * 64

        enforcer.register_hash(content_id, content_hash)

        assert enforcer.verify_hash(content_id, content_hash) is True

    def test_verify_mismatched_hashes_raises_fr13_error(
        self, enforcer: SilentEditEnforcer
    ) -> None:
        """Verify raises FR13ViolationError on hash mismatch (AC2).

        Error message must include "FR13: Silent edit detected - hash mismatch"
        per acceptance criteria.
        """
        content_id = uuid4()
        stored_hash = "c" * 64
        different_hash = "d" * 64

        enforcer.register_hash(content_id, stored_hash)

        with pytest.raises(FR13ViolationError) as exc_info:
            enforcer.verify_hash(content_id, different_hash)

        assert "FR13" in str(exc_info.value)
        assert "Silent edit detected" in str(exc_info.value)
        assert "hash mismatch" in str(exc_info.value)

    def test_verify_unknown_content_returns_true(
        self, enforcer: SilentEditEnforcer
    ) -> None:
        """Verify returns True for unknown content (no stored hash).

        If no hash is stored, we cannot detect a silent edit.
        """
        unknown_id = uuid4()
        any_hash = "e" * 64

        # Should not raise - no stored hash to compare against
        assert enforcer.verify_hash(unknown_id, any_hash) is True

    def test_block_silent_edit_raises_fr13_error(
        self, enforcer: SilentEditEnforcer
    ) -> None:
        """block_silent_edit explicitly raises FR13ViolationError.

        This method is for explicit blocking when a mismatch is detected.
        """
        content_id = uuid4()
        stored_hash = "f" * 64
        computed_hash = "0" * 64

        with pytest.raises(FR13ViolationError) as exc_info:
            enforcer.block_silent_edit(content_id, stored_hash, computed_hash)

        error_msg = str(exc_info.value)
        assert "FR13" in error_msg
        assert "Silent edit detected" in error_msg

    def test_block_silent_edit_includes_hash_info(
        self, enforcer: SilentEditEnforcer
    ) -> None:
        """block_silent_edit error includes hash information for debugging."""
        content_id = uuid4()
        stored_hash = "1" * 64
        computed_hash = "2" * 64

        with pytest.raises(FR13ViolationError) as exc_info:
            enforcer.block_silent_edit(content_id, stored_hash, computed_hash)

        error_msg = str(exc_info.value)
        # Should include partial hashes for debugging
        assert stored_hash[:8] in error_msg or "stored" in error_msg.lower()

    def test_verify_before_publish_with_matching_hash(
        self, enforcer: SilentEditEnforcer
    ) -> None:
        """verify_before_publish succeeds when hash matches (AC1)."""
        content_id = uuid4()
        content = b"test content for publishing"

        # Register hash computed from content
        from src.domain.events.hash_utils import compute_content_hash

        # Create minimal event data for hashing
        event_data = {
            "event_type": "test.event",
            "payload": {"data": "test"},
            "signature": "sig",
            "witness_id": "witness",
            "witness_signature": "wsig",
            "local_timestamp": "2025-01-01T00:00:00Z",
        }
        stored_hash = compute_content_hash(event_data)

        enforcer.register_hash(content_id, stored_hash)

        # Should return True with matching hash
        assert enforcer.verify_before_publish(content_id, stored_hash) is True

    def test_verify_before_publish_with_mismatched_hash_raises(
        self, enforcer: SilentEditEnforcer
    ) -> None:
        """verify_before_publish raises FR13ViolationError on mismatch (AC2)."""
        content_id = uuid4()
        stored_hash = "a" * 64
        computed_hash = "b" * 64

        enforcer.register_hash(content_id, stored_hash)

        with pytest.raises(FR13ViolationError):
            enforcer.verify_before_publish(content_id, computed_hash)

    def test_multiple_content_ids_tracked_independently(
        self, enforcer: SilentEditEnforcer
    ) -> None:
        """Multiple content IDs are tracked independently."""
        content_id_1 = uuid4()
        content_id_2 = uuid4()
        hash_1 = "1" * 64
        hash_2 = "2" * 64

        enforcer.register_hash(content_id_1, hash_1)
        enforcer.register_hash(content_id_2, hash_2)

        assert enforcer.get_stored_hash(content_id_1) == hash_1
        assert enforcer.get_stored_hash(content_id_2) == hash_2

        # Verify correct hash for each
        assert enforcer.verify_hash(content_id_1, hash_1) is True
        assert enforcer.verify_hash(content_id_2, hash_2) is True

        # Cross-verification should fail
        with pytest.raises(FR13ViolationError):
            enforcer.verify_hash(content_id_1, hash_2)
