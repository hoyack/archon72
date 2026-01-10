"""Unit tests for constitutional primitives (FR80, FR81).

These tests verify the constitutional primitives work correctly:
- DeletePreventionMixin (FR80): Prevents deletion of entities
- AtomicOperationContext (FR81): Ensures atomic operations with rollback

All tests are pure unit tests with NO infrastructure dependencies.
"""

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.primitives import AtomicOperationContext, DeletePreventionMixin


class SampleEntity(DeletePreventionMixin):
    """Sample entity for DeletePreventionMixin tests."""

    def __init__(self, name: str = "test") -> None:
        self.name = name


class TestConstitutionalViolationError:
    """Tests for ConstitutionalViolationError."""

    def test_inherits_from_conclave_error(self) -> None:
        """ConstitutionalViolationError should inherit from ConclaveError."""
        from src.domain.exceptions import ConclaveError

        error = ConstitutionalViolationError("Test error")
        assert isinstance(error, ConclaveError)
        assert isinstance(error, Exception)

    def test_error_message_preserved(self) -> None:
        """Error message should be preserved."""
        message = "FR80: Test violation message"
        error = ConstitutionalViolationError(message)
        assert str(error) == message

    def test_empty_message_allowed(self) -> None:
        """Empty message should be allowed."""
        error = ConstitutionalViolationError("")
        assert str(error) == ""


class TestDeletePreventionMixin:
    """Tests for DeletePreventionMixin (FR80)."""

    def test_delete_raises_constitutional_violation(self) -> None:
        """Calling delete() should raise ConstitutionalViolationError."""
        entity = SampleEntity()
        with pytest.raises(ConstitutionalViolationError):
            entity.delete()

    def test_error_message_contains_fr80(self) -> None:
        """Error message should contain FR80 reference."""
        entity = SampleEntity()
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            entity.delete()
        assert "FR80" in str(exc_info.value)

    def test_error_message_contains_deletion_prohibited(self) -> None:
        """Error message should contain 'Deletion prohibited'."""
        entity = SampleEntity()
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            entity.delete()
        assert "Deletion prohibited" in str(exc_info.value)

    def test_error_message_mentions_immutability(self) -> None:
        """Error message should mention entities are immutable."""
        entity = SampleEntity()
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            entity.delete()
        assert "immutable" in str(exc_info.value)

    def test_mixin_does_not_affect_other_methods(self) -> None:
        """Mixin should not affect other entity attributes/methods."""
        entity = SampleEntity(name="test_entity")
        assert entity.name == "test_entity"

    def test_delete_returns_none_type_hint(self) -> None:
        """delete() method should have None return type (raises instead)."""
        # This is a type annotation check - verify the method signature
        from typing import get_type_hints

        hints = get_type_hints(DeletePreventionMixin.delete)
        assert hints.get("return") is type(None)


@pytest.mark.asyncio
class TestAtomicOperationContext:
    """Tests for AtomicOperationContext (FR81)."""

    async def test_no_rollback_on_success(self) -> None:
        """Rollback handlers should NOT be called when no exception."""
        rollback_called = False

        def rollback() -> None:
            nonlocal rollback_called
            rollback_called = True

        async with AtomicOperationContext() as ctx:
            ctx.add_rollback(rollback)
            # No exception - success case

        assert rollback_called is False

    async def test_rollback_on_exception(self) -> None:
        """Rollback handlers should be called when exception occurs."""
        rollback_called = False

        def rollback() -> None:
            nonlocal rollback_called
            rollback_called = True

        with pytest.raises(ValueError):
            async with AtomicOperationContext() as ctx:
                ctx.add_rollback(rollback)
                raise ValueError("Test error")

        assert rollback_called is True

    async def test_exception_reraised_after_rollback(self) -> None:
        """Original exception should be re-raised after rollback."""
        with pytest.raises(ValueError, match="Original error"):
            async with AtomicOperationContext() as ctx:
                ctx.add_rollback(lambda: None)
                raise ValueError("Original error")

    async def test_multiple_rollback_handlers_called_in_reverse(self) -> None:
        """Multiple handlers should be called in reverse (LIFO) order."""
        call_order: list[int] = []

        def make_handler(n: int) -> callable:
            def handler() -> None:
                call_order.append(n)

            return handler

        with pytest.raises(ValueError):
            async with AtomicOperationContext() as ctx:
                ctx.add_rollback(make_handler(1))
                ctx.add_rollback(make_handler(2))
                ctx.add_rollback(make_handler(3))
                raise ValueError("Test error")

        # Should be called in reverse order: 3, 2, 1
        assert call_order == [3, 2, 1]

    async def test_async_rollback_handler(self) -> None:
        """Async rollback handlers should be awaited."""
        rollback_called = False

        async def async_rollback() -> None:
            nonlocal rollback_called
            rollback_called = True

        with pytest.raises(ValueError):
            async with AtomicOperationContext() as ctx:
                ctx.add_rollback(async_rollback)
                raise ValueError("Test error")

        assert rollback_called is True

    async def test_mixed_sync_async_rollback_handlers(self) -> None:
        """Both sync and async handlers should work together."""
        sync_called = False
        async_called = False

        def sync_rollback() -> None:
            nonlocal sync_called
            sync_called = True

        async def async_rollback() -> None:
            nonlocal async_called
            async_called = True

        with pytest.raises(ValueError):
            async with AtomicOperationContext() as ctx:
                ctx.add_rollback(sync_rollback)
                ctx.add_rollback(async_rollback)
                raise ValueError("Test error")

        assert sync_called is True
        assert async_called is True

    async def test_rollback_handler_failure_does_not_stop_others(self) -> None:
        """Failing rollback handler should not prevent other handlers."""
        second_handler_called = False

        def failing_handler() -> None:
            raise RuntimeError("Rollback failed")

        def second_handler() -> None:
            nonlocal second_handler_called
            second_handler_called = True

        with pytest.raises(ValueError):
            async with AtomicOperationContext() as ctx:
                ctx.add_rollback(second_handler)  # Added first, called last
                ctx.add_rollback(failing_handler)  # Added second, called first
                raise ValueError("Test error")

        # Second handler should still be called despite first failing
        assert second_handler_called is True

    async def test_no_handlers_no_error(self) -> None:
        """Context should work fine with no rollback handlers."""
        # No exception case
        async with AtomicOperationContext():
            pass  # No handlers, no exception

        # Exception case with no handlers
        with pytest.raises(ValueError):
            async with AtomicOperationContext():
                raise ValueError("Test")

    async def test_context_returns_self(self) -> None:
        """__aenter__ should return the context itself."""
        async with AtomicOperationContext() as ctx:
            assert isinstance(ctx, AtomicOperationContext)

    async def test_add_rollback_returns_none(self) -> None:
        """add_rollback should return None (not chainable)."""
        async with AtomicOperationContext() as ctx:
            result = ctx.add_rollback(lambda: None)
            assert result is None


class TestNoInfrastructureDependencies:
    """Tests to verify primitives have no infrastructure dependencies."""

    def test_delete_prevention_mixin_no_imports_from_infrastructure(self) -> None:
        """DeletePreventionMixin should not import from infrastructure."""
        import src.domain.primitives.prevent_delete as module

        source_file = module.__file__
        assert source_file is not None

        with open(source_file) as f:
            content = f.read()

        assert "from src.infrastructure" not in content
        assert "import src.infrastructure" not in content

    def test_atomic_operation_context_no_imports_from_infrastructure(self) -> None:
        """AtomicOperationContext should not import from infrastructure."""
        import src.domain.primitives.ensure_atomicity as module

        source_file = module.__file__
        assert source_file is not None

        with open(source_file) as f:
            content = f.read()

        assert "from src.infrastructure" not in content
        assert "import src.infrastructure" not in content

    def test_primitives_init_no_imports_from_infrastructure(self) -> None:
        """Primitives __init__.py should not import from infrastructure."""
        import src.domain.primitives as module

        source_file = module.__file__
        assert source_file is not None

        with open(source_file) as f:
            content = f.read()

        assert "from src.infrastructure" not in content
        assert "import src.infrastructure" not in content
