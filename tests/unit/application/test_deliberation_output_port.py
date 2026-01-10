"""Unit tests for DeliberationOutputPort (Story 2.1, Task 4).

Tests:
- StoredOutput dataclass
- Port interface definition
- No infrastructure imports in port

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- AC1: Immediate Output Commitment
- AC2: Hash Verification on View
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestStoredOutput:
    """Test StoredOutput dataclass."""

    def test_stored_output_creation(self) -> None:
        """StoredOutput can be created with all fields."""
        from src.application.ports.deliberation_output import StoredOutput

        output_id = uuid4()
        stored_at = datetime.now(timezone.utc)
        output = StoredOutput(
            output_id=output_id,
            content_hash="a" * 64,
            event_sequence=42,
            stored_at=stored_at,
        )

        assert output.output_id == output_id
        assert output.content_hash == "a" * 64
        assert output.event_sequence == 42
        assert output.stored_at == stored_at

    def test_stored_output_is_frozen(self) -> None:
        """StoredOutput is immutable (frozen dataclass)."""
        from src.application.ports.deliberation_output import StoredOutput

        output = StoredOutput(
            output_id=uuid4(),
            content_hash="b" * 64,
            event_sequence=1,
            stored_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            output.event_sequence = 99  # type: ignore[misc]


class TestDeliberationOutputPort:
    """Test DeliberationOutputPort abstract interface."""

    def test_port_is_abstract_class(self) -> None:
        """DeliberationOutputPort is an abstract base class."""
        from abc import ABC

        from src.application.ports.deliberation_output import DeliberationOutputPort

        assert issubclass(DeliberationOutputPort, ABC)

    def test_port_has_store_output_method(self) -> None:
        """Port defines store_output abstract method."""
        from src.application.ports.deliberation_output import DeliberationOutputPort

        assert hasattr(DeliberationOutputPort, "store_output")

    def test_port_has_get_output_method(self) -> None:
        """Port defines get_output abstract method."""
        from src.application.ports.deliberation_output import DeliberationOutputPort

        assert hasattr(DeliberationOutputPort, "get_output")

    def test_port_has_verify_hash_method(self) -> None:
        """Port defines verify_hash abstract method."""
        from src.application.ports.deliberation_output import DeliberationOutputPort

        assert hasattr(DeliberationOutputPort, "verify_hash")

    def test_port_cannot_be_instantiated(self) -> None:
        """DeliberationOutputPort cannot be instantiated directly."""
        from src.application.ports.deliberation_output import DeliberationOutputPort

        with pytest.raises(TypeError, match="abstract"):
            DeliberationOutputPort()  # type: ignore[abstract]


class TestNoInfrastructureImports:
    """Verify application port has no infrastructure imports."""

    def test_port_no_infrastructure_imports(self) -> None:
        """deliberation_output.py port has no infrastructure imports."""
        import ast
        from pathlib import Path

        file_path = Path("src/application/ports/deliberation_output.py")
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
