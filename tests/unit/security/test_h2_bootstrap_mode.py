"""Phase 2 Dynamic Testing: H2 - Bootstrap Mode Termination.

Tests the security fix for H2: Witness Bootstrap Allows Unverified Signatures.

The fix adds a configuration flag to disable bootstrap mode after initial setup,
preventing unverified witness signatures from being accepted.
"""

import os
from unittest.mock import patch

import pytest

from src.domain.models.key_generation_ceremony import (
    BootstrapModeDisabledError,
    WITNESS_BOOTSTRAP_ENV_VAR,
    is_witness_bootstrap_enabled,
    validate_bootstrap_mode_for_unverified_witness,
)


class TestIsWitnessBootstrapEnabled:
    """Tests for is_witness_bootstrap_enabled() function."""

    def test_bootstrap_enabled_by_default(self) -> None:
        """Bootstrap mode should be enabled by default for initial setup."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop(WITNESS_BOOTSTRAP_ENV_VAR, None)
            assert is_witness_bootstrap_enabled() is True

    def test_bootstrap_enabled_when_true(self) -> None:
        """Bootstrap mode should be enabled when explicitly set to true."""
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "true"}):
            assert is_witness_bootstrap_enabled() is True

    def test_bootstrap_disabled_when_false(self) -> None:
        """Bootstrap mode should be disabled when set to false."""
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "false"}):
            assert is_witness_bootstrap_enabled() is False

    def test_bootstrap_case_insensitive(self) -> None:
        """Bootstrap mode check should be case insensitive."""
        for value in ["TRUE", "True", "true", "TrUe"]:
            with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: value}):
                assert is_witness_bootstrap_enabled() is True

        for value in ["FALSE", "False", "false", "FaLsE"]:
            with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: value}):
                assert is_witness_bootstrap_enabled() is False


class TestValidateBootstrapModeForUnverifiedWitness:
    """Tests for validate_bootstrap_mode_for_unverified_witness() - the H2 fix."""

    def test_bootstrap_enabled_allows_unverified_witness(self) -> None:
        """When bootstrap is enabled, unverified witnesses should be allowed."""
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "true"}):
            # Should not raise
            validate_bootstrap_mode_for_unverified_witness("KEEPER:alice")

    def test_bootstrap_disabled_rejects_unverified_witness(self) -> None:
        """H2 FIX: When bootstrap is disabled, unverified witnesses should be rejected."""
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "false"}):
            with pytest.raises(BootstrapModeDisabledError) as exc_info:
                validate_bootstrap_mode_for_unverified_witness("KEEPER:alice")

            assert "H2 Security Violation" in str(exc_info.value)
            assert "KEEPER:alice" in str(exc_info.value)
            assert "WITNESS_BOOTSTRAP_ENABLED=false" in str(exc_info.value)

    def test_error_message_includes_witness_id(self) -> None:
        """Error message should include the witness ID for debugging."""
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "false"}):
            with pytest.raises(BootstrapModeDisabledError) as exc_info:
                validate_bootstrap_mode_for_unverified_witness("KEEPER:bob")

            assert "KEEPER:bob" in str(exc_info.value)


class TestH2SecurityScenarios:
    """End-to-end security scenarios for H2 fix."""

    def test_initial_setup_bootstrap_allows_unverified_witnesses(self) -> None:
        """INITIAL SETUP: Unverified witnesses allowed during bootstrap."""
        # During initial setup, WITNESS_BOOTSTRAP_ENABLED=true (default)
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "true"}):
            # Multiple unverified witnesses should be allowed
            validate_bootstrap_mode_for_unverified_witness("KEEPER:founder1")
            validate_bootstrap_mode_for_unverified_witness("KEEPER:founder2")
            validate_bootstrap_mode_for_unverified_witness("KEEPER:founder3")

    def test_post_setup_bootstrap_disabled_blocks_unverified(self) -> None:
        """POST-SETUP: After bootstrap disabled, unverified witnesses blocked."""
        # After initial setup, admin sets WITNESS_BOOTSTRAP_ENABLED=false
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "false"}):
            with pytest.raises(BootstrapModeDisabledError):
                validate_bootstrap_mode_for_unverified_witness("KEEPER:attacker")

    def test_attacker_cannot_add_rogue_witness_post_setup(self) -> None:
        """SECURITY: Attacker cannot add rogue witness after bootstrap disabled."""
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "false"}):
            # Attacker tries to inject a rogue witness
            with pytest.raises(BootstrapModeDisabledError) as exc_info:
                validate_bootstrap_mode_for_unverified_witness("ATTACKER:rogue")

            # Verify the error is informative
            error_msg = str(exc_info.value)
            assert "H2 Security Violation" in error_msg
            assert "ATTACKER:rogue" in error_msg

    def test_legitimate_verified_witness_workflow(self) -> None:
        """Legitimate workflow: verified witnesses don't go through bootstrap check."""
        # Note: In production, verified witnesses skip this validation entirely
        # because their signatures are cryptographically verified.
        # This test just documents the expected flow.

        # The validate_bootstrap_mode_for_unverified_witness() is only called
        # when a witness key is NOT found in the registry. When bootstrap is
        # disabled, this means the witness MUST be registered first.
        pass  # Documented behavior


class TestBootstrapModeTransitions:
    """Tests for transitioning bootstrap mode on/off."""

    def test_enable_to_disable_transition(self) -> None:
        """Transitioning from enabled to disabled should work."""
        # Start with bootstrap enabled
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "true"}):
            assert is_witness_bootstrap_enabled() is True
            validate_bootstrap_mode_for_unverified_witness("KEEPER:test")

        # Disable bootstrap
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "false"}):
            assert is_witness_bootstrap_enabled() is False
            with pytest.raises(BootstrapModeDisabledError):
                validate_bootstrap_mode_for_unverified_witness("KEEPER:test")

    def test_disable_to_enable_transition_requires_explicit_action(self) -> None:
        """Re-enabling bootstrap mode should be an explicit action."""
        # This test documents that re-enabling bootstrap is possible
        # but should be done with care (operational procedure)
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "false"}):
            with pytest.raises(BootstrapModeDisabledError):
                validate_bootstrap_mode_for_unverified_witness("KEEPER:test")

        # Re-enable (only for emergency maintenance)
        with patch.dict(os.environ, {WITNESS_BOOTSTRAP_ENV_VAR: "true"}):
            # Now allowed again
            validate_bootstrap_mode_for_unverified_witness("KEEPER:test")
