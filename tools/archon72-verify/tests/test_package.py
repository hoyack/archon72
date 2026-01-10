"""Tests for package structure (Task 1).

These tests verify:
- Package imports correctly
- CLI entry point exists
- Version is defined
"""

import pytest


def test_package_imports_correctly():
    """Verify archon72_verify package can be imported."""
    import archon72_verify

    # Package should exist
    assert archon72_verify is not None


def test_version_defined():
    """Verify __version__ is defined in package."""
    from archon72_verify import __version__

    # Version should be a non-empty string
    assert isinstance(__version__, str)
    assert len(__version__) > 0
    # Should be semver format (at least X.Y.Z)
    parts = __version__.split(".")
    assert len(parts) >= 3


def test_cli_entry_point_exists():
    """Verify CLI app can be imported."""
    from archon72_verify.cli import app

    # Should be a Typer app
    assert app is not None
    # Should have name attribute
    assert hasattr(app, "info")


def test_package_exports_core_classes():
    """Verify core classes are exported from package."""
    from archon72_verify import ChainVerifier, ObserverClient, VerificationResult

    assert ChainVerifier is not None
    assert ObserverClient is not None
    assert VerificationResult is not None
