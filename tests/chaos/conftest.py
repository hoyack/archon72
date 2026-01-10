"""Chaos test configuration and fixtures (Story 7.9, PM-5).

This module provides shared fixtures and configuration for chaos tests.
Chaos tests are isolated, repeatable tests for destructive/terminal operations.

Constitutional Mandate (PM-5):
Cessation never tested -> Mandatory chaos test in staging, weekly CI.
"""

from __future__ import annotations

import pytest

# Register chaos mark
pytest.register_marker = "chaos: mark test as a chaos test (deselect with '-m \"not chaos\"')"
