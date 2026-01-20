"""Load test harness protocol (Story 2B.7, NFR-10.5).

This module defines the protocol for load testing deliberation systems,
enabling verification of system performance under concurrent load.

Constitutional Constraints:
- NFR-9.4: Load test harness simulates 10k petition flood
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-10.5: Concurrent deliberations - 100+ simultaneous sessions
- CT-11: Silent failure destroys legitimacy - report all failures
- CT-14: Every petition terminates in visible, witnessed fate
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.load_test_config import LoadTestConfig
    from src.domain.models.load_test_metrics import LoadTestMetrics
    from src.domain.models.load_test_report import LoadTestReport


@dataclass
class TestPetition:
    """Represents a test petition for load testing.

    A lightweight petition object used for generating synthetic
    load during performance testing.

    Attributes:
        petition_id: Unique identifier for the petition.
        content: Text content of the petition.
        realm: The realm (domain area) for the petition.
        submitter_id: Optional ID of the submitting entity.
    """

    petition_id: UUID
    content: str
    realm: str
    submitter_id: UUID | None = None


class LoadTestHarnessProtocol(Protocol):
    """Protocol for load testing deliberation systems (Story 2B.7, NFR-10.5).

    Implementations coordinate concurrent deliberation sessions for
    validating system performance under load. The harness manages
    session lifecycle, collects metrics, and generates reports.

    Key Responsibilities:
    - Execute concurrent deliberations up to configured limit
    - Inject failures and timeouts for resilience testing
    - Collect latency and throughput metrics
    - Generate comprehensive test reports

    Constitutional Constraints:
    - NFR-10.1: Verify p95 latency < 5 minutes
    - NFR-10.5: Support 100+ concurrent sessions
    - CT-11: Report all failures (no silent drops)
    - CT-14: Every petition terminates in witnessed fate

    Example:
        >>> harness = LoadTestHarnessService(orchestrator, executor)
        >>> config = LoadTestConfig(concurrent_sessions=100, total_petitions=1000)
        >>> report = await harness.run_load_test(config)
        >>> assert report.nfr_10_1_pass, "p95 latency exceeded 5 minutes"
        >>> assert report.success_rate > 95.0, "Too many failures"
    """

    async def run_load_test(
        self,
        config: LoadTestConfig,
    ) -> LoadTestReport:
        """Execute a load test with the given configuration.

        Runs concurrent deliberations according to the configuration,
        collecting metrics and generating a comprehensive report.

        The test will:
        1. Generate test petitions
        2. Submit petitions in batches
        3. Execute deliberations with concurrency control
        4. Inject failures/timeouts per configuration
        5. Collect latency and resource metrics
        6. Generate final report

        Args:
            config: Load test configuration parameters.

        Returns:
            LoadTestReport with complete metrics and analysis.

        Example:
            >>> config = LoadTestConfig(concurrent_sessions=50)
            >>> report = await harness.run_load_test(config)
            >>> print(report.summary())
        """
        ...

    def generate_test_petitions(
        self,
        count: int,
    ) -> list[TestPetition]:
        """Generate test petitions for load testing.

        Creates synthetic petitions with varied content
        for realistic load testing scenarios.

        Args:
            count: Number of petitions to generate.

        Returns:
            List of TestPetition objects with varied realms and content.

        Example:
            >>> petitions = harness.generate_test_petitions(100)
            >>> assert len(petitions) == 100
            >>> assert all(p.realm in VALID_REALMS for p in petitions)
        """
        ...

    def collect_metrics(self) -> LoadTestMetrics:
        """Collect current load test metrics.

        Returns point-in-time metrics for monitoring test progress.
        Can be called during test execution for real-time monitoring.

        Returns:
            LoadTestMetrics snapshot with current state.

        Example:
            >>> # During test execution
            >>> metrics = harness.collect_metrics()
            >>> print(f"Active: {metrics.active_sessions}")
            >>> print(f"Completed: {metrics.completed_sessions}")
        """
        ...
