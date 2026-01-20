"""Load test configuration (Story 5.8, AC4).

This module provides fixtures and configuration for load testing
the co-sign scalability features.

Load Test Marker:
    @pytest.mark.load - Tests skipped by default, run with:
        pytest -m load tests/load/

Environment Variables:
    CO_SIGN_LOAD_TEST_COUNT: Number of co-signers (default: 1000)
    CO_SIGN_LOAD_TEST_CONCURRENCY: Concurrent insertions (default: 10)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


@dataclass
class LoadTestConfig:
    """Configuration for co-sign load tests.

    Attributes:
        co_signer_count: Total co-signers to insert.
        concurrency: Number of concurrent insertions.
        measure_latency: Whether to track latency percentiles.
        ci_mode: Reduced count for CI (1000 vs 100000).
    """

    co_signer_count: int
    concurrency: int
    measure_latency: bool
    ci_mode: bool


@pytest.fixture
def load_test_config() -> LoadTestConfig:
    """Create load test configuration from environment.

    Environment Variables:
        CO_SIGN_LOAD_TEST_COUNT: Number of co-signers (default: 1000 for CI)
        CO_SIGN_LOAD_TEST_CONCURRENCY: Concurrent insertions (default: 10)
        CO_SIGN_LOAD_TEST_FULL: Set to "1" for full 100k test

    Returns:
        LoadTestConfig with settings from environment.
    """
    full_mode = os.environ.get("CO_SIGN_LOAD_TEST_FULL", "0") == "1"

    if full_mode:
        count = int(os.environ.get("CO_SIGN_LOAD_TEST_COUNT", "100000"))
    else:
        # CI mode - smaller count
        count = int(os.environ.get("CO_SIGN_LOAD_TEST_COUNT", "1000"))

    concurrency = int(os.environ.get("CO_SIGN_LOAD_TEST_CONCURRENCY", "10"))

    return LoadTestConfig(
        co_signer_count=count,
        concurrency=concurrency,
        measure_latency=True,
        ci_mode=not full_mode,
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register load test marker."""
    config.addinivalue_line(
        "markers",
        "load: mark test as load test (skipped by default, run with -m load)",
    )
