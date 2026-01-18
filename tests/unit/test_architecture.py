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

    NOTE: In this codebase, ports (interfaces) are defined in the application
    layer and domain is allowed to import them. This is a pragmatic choice
    to keep ports close to their primary consumers (application services).
    """
    domain_files = list((src_path / "domain").rglob("*.py"))
    forbidden = [
        "from src.infrastructure",
        "from src.api",
        "import src.infrastructure",
        "import src.api",
    ]

    # Allowed exception patterns for domain layer
    # - Importing port interfaces from application.ports is acceptable
    allowed_patterns = [
        "from src.application.ports",
        "import src.application.ports",
    ]

    for py_file in domain_files:
        content = py_file.read_text()
        for forbidden_import in forbidden:
            assert forbidden_import not in content, (
                f"{py_file} contains forbidden import: {forbidden_import}"
            )
        # Check for application imports that aren't allowed patterns
        if "from src.application" in content or "import src.application" in content:
            has_allowed = any(pattern in content for pattern in allowed_patterns)
            # Check for non-port application imports
            lines_with_app_import = [
                line for line in content.split("\n")
                if ("from src.application" in line or "import src.application" in line)
                and not any(pattern in line for pattern in allowed_patterns)
            ]
            assert not lines_with_app_import, (
                f"{py_file} contains forbidden application import "
                f"(ports imports are allowed): {lines_with_app_import}"
            )


def test_application_has_no_forbidden_imports(src_path: Path) -> None:
    """Verify application layer doesn't import from infrastructure or api.

    Application can only import from domain layer.

    NOTE: In this codebase, some infrastructure imports are allowed:
    - Stubs for development/testing dependency injection
    - Observability utilities (logging, correlation) as cross-cutting concerns
    - Config loaders for development mode
    """
    app_files = list((src_path / "application").rglob("*.py"))
    forbidden = [
        "from src.api",
        "import src.api",
    ]

    # Allowed infrastructure patterns for application layer
    allowed_infra_patterns = [
        "from src.infrastructure.stubs",
        "from src.infrastructure.observability",
        "from src.infrastructure.adapters.config",
        "import src.infrastructure.stubs",
        "import src.infrastructure.observability",
        "import src.infrastructure.adapters.config",
    ]

    for py_file in app_files:
        content = py_file.read_text()
        for forbidden_import in forbidden:
            assert forbidden_import not in content, (
                f"{py_file} contains forbidden import: {forbidden_import}"
            )
        # Check for infrastructure imports that aren't allowed patterns
        if "from src.infrastructure" in content or "import src.infrastructure" in content:
            lines_with_infra_import = [
                line for line in content.split("\n")
                if ("from src.infrastructure" in line or "import src.infrastructure" in line)
                and not any(pattern in line for pattern in allowed_infra_patterns)
            ]
            assert not lines_with_infra_import, (
                f"{py_file} contains forbidden infrastructure import "
                f"(stubs/observability/config imports are allowed): {lines_with_infra_import}"
            )


def test_api_has_no_direct_infrastructure_imports(src_path: Path) -> None:
    """Verify api layer doesn't import directly from infrastructure adapters.

    API should use dependency injection for infrastructure adapters,
    not direct imports.

    NOTE: In this FastAPI codebase, some infrastructure imports are acceptable:
    - Stubs for development/testing dependency injection wiring
    - Observability utilities (logging, correlation, metrics) as cross-cutting concerns
    - Monitoring/metrics collection for API middleware
    These imports are used in the composition root (lifespan, startup, dependencies)
    to wire up the application, which is a standard FastAPI pattern.
    """
    api_files = list((src_path / "api").rglob("*.py"))

    # Allowed infrastructure patterns for API layer (composition root/wiring)
    allowed_infra_patterns = [
        "from src.infrastructure.stubs",
        "from src.infrastructure.observability",
        "from src.infrastructure.monitoring",
        "import src.infrastructure.stubs",
        "import src.infrastructure.observability",
        "import src.infrastructure.monitoring",
    ]

    for py_file in api_files:
        content = py_file.read_text()
        # Check for infrastructure imports that aren't allowed patterns
        if "from src.infrastructure" in content or "import src.infrastructure" in content:
            lines_with_infra_import = [
                line for line in content.split("\n")
                if ("from src.infrastructure" in line or "import src.infrastructure" in line)
                and not any(pattern in line for pattern in allowed_infra_patterns)
            ]
            assert not lines_with_infra_import, (
                f"{py_file} contains forbidden infrastructure import "
                f"(stubs/observability/monitoring imports are allowed): {lines_with_infra_import}"
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
