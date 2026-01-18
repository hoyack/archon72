"""Integration tests for the import boundary checking script.

These tests verify that the check_imports.py script works correctly
as a standalone tool and can be used with pre-commit hooks.

Note: These tests are self-contained and don't require testcontainers
or database/redis fixtures from conftest.py.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

# Get project root for running commands
PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.mark.integration
class TestImportBoundaryScript:
    """Integration tests for the check_imports.py script."""

    def test_script_runs_successfully_on_clean_codebase(self) -> None:
        """Verify check_imports.py runs without errors on clean codebase."""
        result = subprocess.run(
            ["python3", "scripts/check_imports.py"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"Import check failed: {result.stderr}"
        assert "No import boundary violations found" in result.stdout

    def test_script_detects_domain_infrastructure_violation(self) -> None:
        """Verify script detects domain importing from infrastructure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal src structure with a violation
            src_dir = Path(tmpdir) / "src"
            domain_dir = src_dir / "domain"
            infra_dir = src_dir / "infrastructure"

            domain_dir.mkdir(parents=True)
            infra_dir.mkdir(parents=True)

            # Create violation file
            violation_file = domain_dir / "bad_import.py"
            violation_file.write_text("from src.infrastructure import something")

            result = subprocess.run(
                ["python3", "scripts/check_imports.py", str(src_dir)],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            assert result.returncode == 1
            assert "domain layer cannot import from infrastructure" in result.stdout

    def test_script_allows_valid_application_domain_import(self) -> None:
        """Verify script allows application importing from domain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal src structure with valid import
            src_dir = Path(tmpdir) / "src"
            domain_dir = src_dir / "domain"
            app_dir = src_dir / "application"

            domain_dir.mkdir(parents=True)
            app_dir.mkdir(parents=True)

            # Create valid import file
            valid_file = app_dir / "valid_import.py"
            valid_file.write_text("from src.domain.models import MyModel")

            result = subprocess.run(
                ["python3", "scripts/check_imports.py", str(src_dir)],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            assert result.returncode == 0
            assert "No import boundary violations found" in result.stdout

    def test_script_reports_file_and_line_number(self) -> None:
        """Verify script reports violations with file:line format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            domain_dir = src_dir / "domain"
            domain_dir.mkdir(parents=True)

            # Create violation on specific line
            violation_file = domain_dir / "test_module.py"
            violation_file.write_text(
                "import os\n"  # Line 1 - valid
                "import sys\n"  # Line 2 - valid
                "from src.infrastructure import something\n"  # Line 3 - violation
            )

            result = subprocess.run(
                ["python3", "scripts/check_imports.py", str(src_dir)],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            assert result.returncode == 1
            # Should report the violation with line number 3
            assert ":3:" in result.stdout

    def test_script_counts_total_violations(self) -> None:
        """Verify script counts and reports total violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            domain_dir = src_dir / "domain"
            domain_dir.mkdir(parents=True)

            # Create file with multiple violations
            violation_file = domain_dir / "many_violations.py"
            violation_file.write_text(
                "from src.infrastructure import a\n"
                "from src.application import b\n"
                "from src.api import c\n"
            )

            result = subprocess.run(
                ["python3", "scripts/check_imports.py", str(src_dir)],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            assert result.returncode == 1
            assert "Total: 3 violation(s)" in result.stdout


@pytest.mark.integration
class TestMakefileTargets:
    """Integration tests for Makefile targets."""

    def test_make_check_imports_runs(self) -> None:
        """Verify make check-imports target works."""
        result = subprocess.run(
            ["make", "check-imports"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "No import boundary violations found" in result.stdout
