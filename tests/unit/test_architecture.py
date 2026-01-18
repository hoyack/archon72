"""Tests to verify hexagonal architecture structure."""

from pathlib import Path

import pytest

# Compute project root relative to this test file
PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture
def src_path() -> Path:
    """Return the src directory path."""
    return PROJECT_ROOT / "src"


def test_main_layers_exist(src_path: Path) -> None:
    """Verify all main layer directories exist."""
    layers = ["domain", "application", "infrastructure", "api"]
    for layer in layers:
        assert (src_path / layer).is_dir(), f"Missing layer: {layer}"
        assert (src_path / layer / "__init__.py").is_file(), (
            f"Missing {layer}/__init__.py"
        )
        assert (src_path / layer / "README.md").is_file(), f"Missing {layer}/README.md"


def test_domain_subdirectories_exist(src_path: Path) -> None:
    """Verify domain layer has required subdirectories."""
    domain = src_path / "domain"
    subdirs = ["events", "entities", "value_objects", "ports"]
    for subdir in subdirs:
        assert (domain / subdir).is_dir(), f"Missing domain subdir: {subdir}"
        assert (domain / subdir / "__init__.py").is_file(), (
            f"Missing {subdir}/__init__.py"
        )


def test_domain_has_no_external_layer_imports(src_path: Path) -> None:
    """Verify domain layer imports NOTHING from other layers.

    Domain is the innermost layer and must remain pure - no dependencies
    on application, infrastructure, or api layers.
    """
    domain_files = list((src_path / "domain").rglob("*.py"))
    forbidden = [
        "from src.application",
        "from src.infrastructure",
        "from src.api",
        "import src.application",
        "import src.infrastructure",
        "import src.api",
    ]

    for py_file in domain_files:
        content = py_file.read_text()
        for forbidden_import in forbidden:
            assert forbidden_import not in content, (
                f"{py_file} contains forbidden import: {forbidden_import}"
            )


def test_application_has_no_forbidden_imports(src_path: Path) -> None:
    """Verify application layer doesn't import from infrastructure or api.

    Application can only import from domain layer.
    """
    app_files = list((src_path / "application").rglob("*.py"))
    forbidden = [
        "from src.infrastructure",
        "from src.api",
        "import src.infrastructure",
        "import src.api",
    ]

    for py_file in app_files:
        content = py_file.read_text()
        for forbidden_import in forbidden:
            assert forbidden_import not in content, (
                f"{py_file} contains forbidden import: {forbidden_import}"
            )


def test_api_has_no_direct_infrastructure_imports(src_path: Path) -> None:
    """Verify api layer doesn't import directly from infrastructure.

    API should use dependency injection for infrastructure adapters,
    not direct imports.
    """
    api_files = list((src_path / "api").rglob("*.py"))
    forbidden = [
        "from src.infrastructure",
        "import src.infrastructure",
    ]

    for py_file in api_files:
        content = py_file.read_text()
        for forbidden_import in forbidden:
            assert forbidden_import not in content, (
                f"{py_file} contains forbidden import: {forbidden_import}"
            )


def test_conclave_error_exists() -> None:
    """Verify base exception class is defined."""
    from src.domain.exceptions import ConclaveError

    assert issubclass(ConclaveError, Exception)


def test_conclave_error_importable_from_domain() -> None:
    """Verify ConclaveError is exported from domain __init__."""
    from src.domain import ConclaveError

    assert issubclass(ConclaveError, Exception)


def test_conclave_error_accepts_message() -> None:
    """Verify ConclaveError can be instantiated with a message."""
    from src.domain.exceptions import ConclaveError

    error = ConclaveError("test message")
    assert str(error) == "test message"

    # Also verify default empty message works
    error_default = ConclaveError()
    assert str(error_default) == ""


def test_layer_readme_content(src_path: Path) -> None:
    """Verify each layer README has meaningful content."""
    layers = ["domain", "application", "infrastructure", "api"]

    for layer in layers:
        readme = src_path / layer / "README.md"
        content = readme.read_text()
        # Each README should have a title and import rules
        assert f"# {layer.title()}" in content or f"# {layer.upper()}" in content, (
            f"{layer}/README.md missing title"
        )
        assert "Import" in content, f"{layer}/README.md missing import rules section"
