"""Unit tests for NoPreviewEnforcer domain service (Story 2.1, Task 2).

Tests:
- Commit output tracking
- Verify committed status
- FR9ViolationError on uncommitted access

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- AC3: Pre-Commit Access Denial
- AC4: No Preview Code Path
"""

from __future__ import annotations

from uuid import uuid4

import pytest


class TestFR9ViolationError:
    """Test FR9ViolationError exception."""

    def test_fr9_error_is_constitutional_violation(self) -> None:
        """FR9ViolationError inherits from ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.errors.no_preview import FR9ViolationError

        assert issubclass(FR9ViolationError, ConstitutionalViolationError)

    def test_fr9_error_message(self) -> None:
        """FR9ViolationError can be raised with message."""
        from src.domain.errors.no_preview import FR9ViolationError

        error = FR9ViolationError("FR9: Output must be recorded before viewing")
        assert "FR9" in str(error)
        assert "recorded before viewing" in str(error)


class TestNoPreviewEnforcer:
    """Test NoPreviewEnforcer domain service."""

    def test_mark_committed_stores_output_id(self) -> None:
        """mark_committed stores output_id as committed."""
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()

        enforcer.mark_committed(output_id)

        assert enforcer.is_committed(output_id) is True

    def test_is_committed_returns_false_for_unknown_output(self) -> None:
        """is_committed returns False for unknown output_id."""
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()

        assert enforcer.is_committed(output_id) is False

    def test_verify_committed_returns_true_for_committed_output(self) -> None:
        """verify_committed returns True for committed output."""
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()
        enforcer.mark_committed(output_id)

        assert enforcer.verify_committed(output_id) is True

    def test_verify_committed_raises_fr9_for_uncommitted_output(self) -> None:
        """verify_committed raises FR9ViolationError for uncommitted output."""
        from src.domain.errors.no_preview import FR9ViolationError
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()

        with pytest.raises(FR9ViolationError) as exc_info:
            enforcer.verify_committed(output_id)

        assert "FR9" in str(exc_info.value)
        assert "recorded before viewing" in str(exc_info.value)

    def test_enforce_no_preview_raises_for_uncommitted(self) -> None:
        """enforce_no_preview raises FR9ViolationError for uncommitted output."""
        from src.domain.errors.no_preview import FR9ViolationError
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()

        with pytest.raises(FR9ViolationError):
            enforcer.enforce_no_preview(output_id)

    def test_enforce_no_preview_passes_for_committed(self) -> None:
        """enforce_no_preview does not raise for committed output."""
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()
        enforcer.mark_committed(output_id)

        # Should not raise
        enforcer.enforce_no_preview(output_id)


class TestNoPreviewEnforcerHashVerification:
    """Test hash verification functionality."""

    def test_mark_committed_with_hash_stores_hash(self) -> None:
        """mark_committed stores content_hash with output_id."""
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()
        content_hash = "a" * 64

        enforcer.mark_committed(output_id, content_hash=content_hash)

        assert enforcer.get_content_hash(output_id) == content_hash

    def test_verify_hash_returns_true_for_matching_hash(self) -> None:
        """verify_hash returns True when hashes match."""
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()
        content_hash = "b" * 64

        enforcer.mark_committed(output_id, content_hash=content_hash)

        assert enforcer.verify_hash(output_id, content_hash) is True

    def test_verify_hash_raises_fr9_for_mismatch(self) -> None:
        """verify_hash raises FR9ViolationError for hash mismatch."""
        from src.domain.errors.no_preview import FR9ViolationError
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()
        stored_hash = "c" * 64
        wrong_hash = "d" * 64

        enforcer.mark_committed(output_id, content_hash=stored_hash)

        with pytest.raises(FR9ViolationError) as exc_info:
            enforcer.verify_hash(output_id, wrong_hash)

        assert "hash mismatch" in str(exc_info.value).lower()

    def test_get_content_hash_returns_none_for_uncommitted(self) -> None:
        """get_content_hash returns None for uncommitted output."""
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()

        assert enforcer.get_content_hash(output_id) is None


class TestNoPreviewEnforcerFR13Integration:
    """Test FR13 (No Silent Edits) integration (Story 2.5)."""

    def test_verify_hash_for_publish_raises_fr13_for_mismatch(self) -> None:
        """verify_hash_for_publish raises FR13ViolationError for hash mismatch."""
        from src.domain.errors.silent_edit import FR13ViolationError
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()
        stored_hash = "a" * 64
        wrong_hash = "b" * 64

        enforcer.mark_committed(output_id, content_hash=stored_hash)

        with pytest.raises(FR13ViolationError) as exc_info:
            enforcer.verify_hash_for_publish(output_id, wrong_hash)

        assert "FR13" in str(exc_info.value)
        assert "Silent edit detected" in str(exc_info.value)

    def test_verify_hash_for_publish_returns_true_for_match(self) -> None:
        """verify_hash_for_publish returns True when hashes match."""
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()
        content_hash = "c" * 64

        enforcer.mark_committed(output_id, content_hash=content_hash)

        assert enforcer.verify_hash_for_publish(output_id, content_hash) is True

    def test_verify_hash_for_publish_returns_true_no_stored_hash(self) -> None:
        """verify_hash_for_publish returns True if no stored hash (cannot verify)."""
        from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

        enforcer = NoPreviewEnforcer()
        output_id = uuid4()
        any_hash = "d" * 64

        # Mark committed but without hash
        enforcer.mark_committed(output_id)

        assert enforcer.verify_hash_for_publish(output_id, any_hash) is True

    def test_fr9_and_fr13_errors_are_distinct(self) -> None:
        """FR9 and FR13 errors are distinct classes."""
        from src.domain.errors.no_preview import FR9ViolationError
        from src.domain.errors.silent_edit import FR13ViolationError

        assert FR9ViolationError is not FR13ViolationError
        assert not issubclass(FR9ViolationError, FR13ViolationError)
        assert not issubclass(FR13ViolationError, FR9ViolationError)


class TestNoInfrastructureImports:
    """Verify domain service has no infrastructure imports."""

    def test_no_preview_enforcer_no_infrastructure_imports(self) -> None:
        """no_preview_enforcer.py has no infrastructure imports."""
        import ast
        from pathlib import Path

        file_path = Path("src/domain/services/no_preview_enforcer.py")
        source = file_path.read_text()
        tree = ast.parse(source)

        forbidden_modules = ["src.infrastructure", "sqlalchemy", "redis", "supabase"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_modules:
                        assert not node.module.startswith(forbidden), (
                            f"Forbidden import: {node.module}"
                        )
