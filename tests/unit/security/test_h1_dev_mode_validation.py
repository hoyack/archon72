"""Phase 2 Dynamic Testing: H1 - DEV_MODE/ENVIRONMENT Validation.

Tests the security fix for H1: Environment Variable Controls Critical Security Boundary.

The fix adds secondary validation that prevents DEV_MODE=true in production environments.
"""

import os
from unittest.mock import patch

import pytest

from src.domain.models.signable import (
    DevModeEnvironmentMismatchError,
    PRODUCTION_ENVIRONMENTS,
    _detect_environment,
    _is_production_environment,
    is_dev_mode,
    validate_dev_mode_consistency,
)


class TestIsDevMode:
    """Tests for is_dev_mode() function."""

    def test_dev_mode_true_when_set(self) -> None:
        """DEV_MODE=true should return True."""
        with patch.dict(os.environ, {"DEV_MODE": "true"}):
            assert is_dev_mode() is True

    def test_dev_mode_false_when_set(self) -> None:
        """DEV_MODE=false should return False."""
        with patch.dict(os.environ, {"DEV_MODE": "false"}):
            assert is_dev_mode() is False

    def test_dev_mode_false_when_unset(self) -> None:
        """DEV_MODE unset should default to False."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove DEV_MODE if present
            os.environ.pop("DEV_MODE", None)
            assert is_dev_mode() is False

    def test_dev_mode_case_insensitive(self) -> None:
        """DEV_MODE should be case insensitive."""
        for value in ["TRUE", "True", "true", "TrUe"]:
            with patch.dict(os.environ, {"DEV_MODE": value}):
                assert is_dev_mode() is True


class TestEnvironmentDetection:
    """Tests for environment detection functions."""

    def test_detect_development_default(self) -> None:
        """ENVIRONMENT unset should default to development."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ENVIRONMENT", None)
            assert _detect_environment() == "development"

    def test_detect_production(self) -> None:
        """ENVIRONMENT=production should be detected."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert _detect_environment() == "production"

    def test_detect_environment_case_insensitive(self) -> None:
        """Environment detection should be case insensitive."""
        with patch.dict(os.environ, {"ENVIRONMENT": "PRODUCTION"}):
            assert _detect_environment() == "production"

    def test_is_production_environment_true(self) -> None:
        """Should recognize production environments."""
        for env in PRODUCTION_ENVIRONMENTS:
            with patch.dict(os.environ, {"ENVIRONMENT": env}):
                assert _is_production_environment() is True

    def test_is_production_environment_false(self) -> None:
        """Should not recognize non-production environments."""
        for env in ["development", "test", "local", "dev"]:
            with patch.dict(os.environ, {"ENVIRONMENT": env}):
                assert _is_production_environment() is False


class TestValidateDevModeConsistency:
    """Tests for validate_dev_mode_consistency() - the H1 fix."""

    def test_dev_mode_in_production_raises_error(self) -> None:
        """H1 FIX: DEV_MODE=true in production should raise error."""
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "production"}):
            with pytest.raises(DevModeEnvironmentMismatchError) as exc_info:
                validate_dev_mode_consistency()

            assert "H1 Security Violation" in str(exc_info.value)
            assert "DEV_MODE=true is not allowed" in str(exc_info.value)

    def test_dev_mode_in_staging_raises_error(self) -> None:
        """H1 FIX: DEV_MODE=true in staging should raise error."""
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "staging"}):
            with pytest.raises(DevModeEnvironmentMismatchError):
                validate_dev_mode_consistency()

    def test_dev_mode_in_prod_alias_raises_error(self) -> None:
        """H1 FIX: DEV_MODE=true in prod should raise error."""
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "prod"}):
            with pytest.raises(DevModeEnvironmentMismatchError):
                validate_dev_mode_consistency()

    def test_dev_mode_in_development_allowed(self) -> None:
        """DEV_MODE=true in development should be allowed."""
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "development"}):
            # Should not raise
            validate_dev_mode_consistency()

    def test_dev_mode_in_test_allowed(self) -> None:
        """DEV_MODE=true in test should be allowed."""
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "test"}):
            # Should not raise
            validate_dev_mode_consistency()

    def test_production_mode_in_production_allowed(self) -> None:
        """DEV_MODE=false in production should be allowed."""
        with patch.dict(os.environ, {"DEV_MODE": "false", "ENVIRONMENT": "production"}):
            # Should not raise
            validate_dev_mode_consistency()

    def test_production_mode_in_development_allowed(self) -> None:
        """DEV_MODE=false in development should be allowed (logs info)."""
        with patch.dict(os.environ, {"DEV_MODE": "false", "ENVIRONMENT": "development"}):
            # Should not raise
            validate_dev_mode_consistency()


class TestH1SecurityScenarios:
    """End-to-end security scenarios for H1 fix."""

    def test_attacker_cannot_force_dev_mode_in_production(self) -> None:
        """SECURITY: Attacker setting DEV_MODE=true in production is blocked."""
        # Simulate attacker modifying environment
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "production"}):
            with pytest.raises(DevModeEnvironmentMismatchError):
                validate_dev_mode_consistency()

    def test_legitimate_dev_setup_works(self) -> None:
        """Normal development setup should work without issues."""
        with patch.dict(os.environ, {"DEV_MODE": "true", "ENVIRONMENT": "development"}):
            validate_dev_mode_consistency()  # Should not raise

    def test_legitimate_production_setup_works(self) -> None:
        """Normal production setup should work without issues."""
        with patch.dict(os.environ, {"DEV_MODE": "false", "ENVIRONMENT": "production"}):
            validate_dev_mode_consistency()  # Should not raise
