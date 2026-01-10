"""Chaos tests for Archon 72 Conclave Backend.

Chaos tests verify destructive/terminal operations like cessation
that require special isolation and cannot pollute shared state.

These tests are separate from unit and integration tests and are
marked with @pytest.mark.chaos for selective execution.

Constitutional Mandate (PM-5):
Cessation never tested -> Mandatory chaos test in staging, weekly CI
"""
