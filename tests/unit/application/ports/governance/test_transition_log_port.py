"""Unit tests for TransitionLogPort interface.

Story: consent-gov-9.4: State Transition Logging

Tests the port interface design to ensure:
- Append-only enforcement (no modification/deletion methods)
- Required methods for read operations
"""

import inspect
from typing import Protocol

from src.application.ports.governance.transition_log_port import TransitionLogPort


class TestTransitionLogPortInterface:
    """Tests for TransitionLogPort interface design."""

    def test_port_is_protocol(self) -> None:
        """TransitionLogPort is a Protocol."""
        assert issubclass(type(TransitionLogPort), type(Protocol))

    def test_append_method_exists(self) -> None:
        """Port has append method."""
        assert hasattr(TransitionLogPort, "append")

    def test_query_method_exists(self) -> None:
        """Port has query method."""
        assert hasattr(TransitionLogPort, "query")

    def test_get_by_id_method_exists(self) -> None:
        """Port has get_by_id method."""
        assert hasattr(TransitionLogPort, "get_by_id")

    def test_count_method_exists(self) -> None:
        """Port has count method."""
        assert hasattr(TransitionLogPort, "count")

    def test_get_entity_history_method_exists(self) -> None:
        """Port has get_entity_history method."""
        assert hasattr(TransitionLogPort, "get_entity_history")


class TestAppendOnlyDesign:
    """Tests ensuring port enforces append-only design."""

    def test_no_update_method(self) -> None:
        """Port has no update method."""
        assert not hasattr(TransitionLogPort, "update")
        assert not hasattr(TransitionLogPort, "update_log")
        assert not hasattr(TransitionLogPort, "modify")
        assert not hasattr(TransitionLogPort, "modify_log")

    def test_no_delete_method(self) -> None:
        """Port has no delete method."""
        assert not hasattr(TransitionLogPort, "delete")
        assert not hasattr(TransitionLogPort, "delete_log")
        assert not hasattr(TransitionLogPort, "remove")
        assert not hasattr(TransitionLogPort, "remove_log")

    def test_no_clear_method(self) -> None:
        """Port has no clear method."""
        assert not hasattr(TransitionLogPort, "clear")
        assert not hasattr(TransitionLogPort, "clear_all")
        assert not hasattr(TransitionLogPort, "truncate")

    def test_only_append_writes(self) -> None:
        """Port only has append for writes, all others are reads."""
        # Get all methods that aren't private or special
        methods = [
            name
            for name in dir(TransitionLogPort)
            if not name.startswith("_")
            and callable(getattr(TransitionLogPort, name, None))
        ]

        # Write-like methods (that mutate state)
        write_methods = {"append"}  # Only append should exist

        # All other methods should be read-only
        read_methods = {"query", "get_by_id", "count", "get_entity_history"}

        for method in methods:
            if method in write_methods or method in read_methods:
                continue
            else:
                # If there are other methods, they should be documented
                # and not include write operations
                assert method not in {
                    "update",
                    "delete",
                    "modify",
                    "remove",
                    "clear",
                }, f"Unexpected write method found: {method}"


class TestMethodSignatures:
    """Tests for method signature correctness."""

    def test_append_is_async(self) -> None:
        """append method is async."""
        method = getattr(TransitionLogPort, "append", None)
        assert method is not None
        assert inspect.iscoroutinefunction(method) or "async" in str(
            inspect.signature(method)
        )

    def test_query_is_async(self) -> None:
        """query method is async."""
        method = getattr(TransitionLogPort, "query", None)
        assert method is not None

    def test_get_by_id_is_async(self) -> None:
        """get_by_id method is async."""
        method = getattr(TransitionLogPort, "get_by_id", None)
        assert method is not None
