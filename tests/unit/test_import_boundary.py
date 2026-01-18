"""Unit tests for the import boundary checking script.

Tests verify that the hexagonal architecture import rules are enforced:
- domain/ imports NOTHING from other src layers
- application/ imports from domain/ only
- infrastructure/ imports from domain/ and application/
- api/ imports from application/ (and transitively domain/)
"""

import ast

# Import from scripts directory
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from check_imports import (
    ALLOWED_IMPORTS,
    LAYER_HIERARCHY,
    check_file_imports,
    check_import_boundaries,
    get_import_module,
)


class TestLayerHierarchy:
    """Test that the layer hierarchy is correctly defined."""

    def test_domain_is_innermost(self) -> None:
        """Domain should be the innermost layer (level 0)."""
        assert LAYER_HIERARCHY["domain"] == 0

    def test_application_is_level_1(self) -> None:
        """Application should be level 1."""
        assert LAYER_HIERARCHY["application"] == 1

    def test_infrastructure_is_level_2(self) -> None:
        """Infrastructure should be level 2."""
        assert LAYER_HIERARCHY["infrastructure"] == 2

    def test_api_is_outermost(self) -> None:
        """API should be the outermost layer (level 3)."""
        assert LAYER_HIERARCHY["api"] == 3


class TestAllowedImports:
    """Test that the allowed imports are correctly defined."""

    def test_domain_imports_nothing(self) -> None:
        """Domain should not be allowed to import any src layers."""
        assert ALLOWED_IMPORTS["domain"] == set()

    def test_application_imports_domain_only(self) -> None:
        """Application can only import from domain."""
        assert ALLOWED_IMPORTS["application"] == {"domain"}

    def test_infrastructure_imports_domain_and_application(self) -> None:
        """Infrastructure can import from domain and application."""
        assert ALLOWED_IMPORTS["infrastructure"] == {"domain", "application"}

    def test_api_imports_application_and_domain(self) -> None:
        """API can import from application and domain."""
        assert ALLOWED_IMPORTS["api"] == {"application", "domain"}


class TestGetImportModule:
    """Test the get_import_module helper function."""

    def test_import_from_statement(self) -> None:
        """Test extraction from 'from x import y' statement."""
        code = "from src.domain.models import MyModel"
        tree = ast.parse(code)
        node = tree.body[0]
        assert isinstance(node, ast.ImportFrom)
        assert get_import_module(node) == "src.domain.models"

    def test_import_statement(self) -> None:
        """Test extraction from 'import x' statement."""
        code = "import src.domain.models"
        tree = ast.parse(code)
        node = tree.body[0]
        assert isinstance(node, ast.Import)
        assert get_import_module(node) == "src.domain.models"

    def test_none_for_relative_import(self) -> None:
        """Test that relative imports return None for module."""
        code = "from . import something"
        tree = ast.parse(code)
        node = tree.body[0]
        assert isinstance(node, ast.ImportFrom)
        # Relative imports have module=None
        assert get_import_module(node) is None


class TestCheckFileImports:
    """Test the check_file_imports function with temporary files."""

    @pytest.fixture
    def temp_src_dir(self) -> Path:
        """Create a temporary src directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()

            # Create layer directories
            for layer in ["domain", "application", "infrastructure", "api"]:
                (src_dir / layer).mkdir()
                (src_dir / layer / "__init__.py").write_text("")

            yield src_dir

    def test_valid_import_domain_to_stdlib(self, temp_src_dir: Path) -> None:
        """Domain can import from standard library."""
        domain_file = temp_src_dir / "domain" / "test_module.py"
        domain_file.write_text("import os\nimport sys\nfrom typing import List")

        violations = check_file_imports(domain_file, temp_src_dir)
        assert violations == []

    def test_valid_import_application_to_domain(self, temp_src_dir: Path) -> None:
        """Application can import from domain."""
        app_file = temp_src_dir / "application" / "test_service.py"
        app_file.write_text("from src.domain.models import MyModel")

        violations = check_file_imports(app_file, temp_src_dir)
        assert violations == []

    def test_valid_import_infrastructure_to_domain(self, temp_src_dir: Path) -> None:
        """Infrastructure can import from domain."""
        infra_file = temp_src_dir / "infrastructure" / "test_adapter.py"
        infra_file.write_text("from src.domain.models import MyModel")

        violations = check_file_imports(infra_file, temp_src_dir)
        assert violations == []

    def test_valid_import_infrastructure_to_application(
        self, temp_src_dir: Path
    ) -> None:
        """Infrastructure can import from application (for ports)."""
        infra_file = temp_src_dir / "infrastructure" / "test_adapter.py"
        infra_file.write_text("from src.application.ports import HSMPort")

        violations = check_file_imports(infra_file, temp_src_dir)
        assert violations == []

    def test_valid_import_api_to_application(self, temp_src_dir: Path) -> None:
        """API can import from application."""
        api_file = temp_src_dir / "api" / "test_route.py"
        api_file.write_text("from src.application.services import MyService")

        violations = check_file_imports(api_file, temp_src_dir)
        assert violations == []

    def test_valid_same_layer_import(self, temp_src_dir: Path) -> None:
        """Same-layer imports should be allowed."""
        domain_file = temp_src_dir / "domain" / "test_module.py"
        domain_file.write_text("from src.domain.other import Something")

        violations = check_file_imports(domain_file, temp_src_dir)
        assert violations == []

    def test_violation_domain_imports_infrastructure(self, temp_src_dir: Path) -> None:
        """Domain importing infrastructure should be detected."""
        domain_file = temp_src_dir / "domain" / "bad_module.py"
        domain_file.write_text("from src.infrastructure.adapters import SomeAdapter")

        violations = check_file_imports(domain_file, temp_src_dir)
        assert len(violations) == 1
        assert violations[0][0] == str(domain_file)
        assert violations[0][1] == 1  # Line number
        assert "domain layer cannot import from infrastructure" in violations[0][2]

    def test_violation_domain_imports_application(self, temp_src_dir: Path) -> None:
        """Domain importing application should be detected."""
        domain_file = temp_src_dir / "domain" / "bad_module.py"
        domain_file.write_text("from src.application.services import SomeService")

        violations = check_file_imports(domain_file, temp_src_dir)
        assert len(violations) == 1
        assert "domain layer cannot import from application" in violations[0][2]

    def test_violation_domain_imports_api(self, temp_src_dir: Path) -> None:
        """Domain importing api should be detected."""
        domain_file = temp_src_dir / "domain" / "bad_module.py"
        domain_file.write_text("from src.api.routes import something")

        violations = check_file_imports(domain_file, temp_src_dir)
        assert len(violations) == 1
        assert "domain layer cannot import from api" in violations[0][2]

    def test_violation_application_imports_infrastructure(
        self, temp_src_dir: Path
    ) -> None:
        """Application importing infrastructure should be detected."""
        app_file = temp_src_dir / "application" / "bad_service.py"
        app_file.write_text("from src.infrastructure.adapters import SomeAdapter")

        violations = check_file_imports(app_file, temp_src_dir)
        assert len(violations) == 1
        assert "application layer cannot import from infrastructure" in violations[0][2]

    def test_violation_application_imports_api(self, temp_src_dir: Path) -> None:
        """Application importing api should be detected."""
        app_file = temp_src_dir / "application" / "bad_service.py"
        app_file.write_text("from src.api.routes import something")

        violations = check_file_imports(app_file, temp_src_dir)
        assert len(violations) == 1
        assert "application layer cannot import from api" in violations[0][2]

    def test_violation_infrastructure_imports_api(self, temp_src_dir: Path) -> None:
        """Infrastructure importing api should be detected."""
        infra_file = temp_src_dir / "infrastructure" / "bad_adapter.py"
        infra_file.write_text("from src.api.routes import something")

        violations = check_file_imports(infra_file, temp_src_dir)
        assert len(violations) == 1
        assert "infrastructure layer cannot import from api" in violations[0][2]

    def test_violation_api_imports_infrastructure(self, temp_src_dir: Path) -> None:
        """API importing infrastructure should be detected."""
        api_file = temp_src_dir / "api" / "bad_route.py"
        api_file.write_text("from src.infrastructure.adapters import SomeAdapter")

        violations = check_file_imports(api_file, temp_src_dir)
        assert len(violations) == 1
        assert "api layer cannot import from infrastructure" in violations[0][2]

    def test_multiple_violations_in_single_file(self, temp_src_dir: Path) -> None:
        """Multiple violations in one file should all be detected."""
        domain_file = temp_src_dir / "domain" / "very_bad_module.py"
        domain_file.write_text(
            "from src.infrastructure.adapters import A\n"
            "from src.application.services import B\n"
            "from src.api.routes import C\n"
        )

        violations = check_file_imports(domain_file, temp_src_dir)
        assert len(violations) == 3


class TestCheckImportBoundaries:
    """Test the main check_import_boundaries function."""

    def test_empty_directory(self) -> None:
        """Should handle empty directory gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()

            violations = check_import_boundaries(src_dir)
            assert violations == []

    def test_nonexistent_directory(self) -> None:
        """Should handle nonexistent directory gracefully."""
        violations = check_import_boundaries(Path("/nonexistent/path"))
        assert violations == []

    def test_scans_all_python_files(self) -> None:
        """Should scan all .py files recursively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            domain_dir = src_dir / "domain" / "subdir"
            domain_dir.mkdir(parents=True)

            # Create a violation in a nested file
            nested_file = domain_dir / "nested.py"
            nested_file.write_text("from src.infrastructure import something")

            violations = check_import_boundaries(src_dir)
            assert len(violations) == 1
            assert "nested.py" in violations[0][0]
