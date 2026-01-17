"""Test helpers for Archon 72 tests.

This package contains reusable test utilities and fake implementations
for dependency injection in unit tests.

Helpers:
    FakeTimeAuthority: Controllable time authority for deterministic tests

Usage:
    from tests.helpers import FakeTimeAuthority
"""

from tests.helpers.fake_time_authority import FakeTimeAuthority

__all__ = ["FakeTimeAuthority"]
