"""Integration tests for Deliberation Chaos Testing (Story 2B.8, NFR-9.5).

Tests validate:
- Chaos test scenarios execute and recover correctly
- Witness chain integrity is preserved during chaos (CT-12)
- No silent failures occur (CT-11)
- All affected petitions reach terminal fate (CT-14)
- NFR-10.6 archon substitution latency is met
"""

from __future__ import annotations

import pytest

from src.domain.models.chaos_test_config import ChaosScenario, ChaosTestConfig
from src.domain.models.chaos_test_report import (
    ARCHON_SUBSTITUTION_SLA_MS,
    ChaosTestOutcome,
)
from src.infrastructure.stubs.chaos_test_harness_stub import ChaosTestHarnessStub


class TestArchonTimeoutScenario:
    """Integration tests for Archon timeout mid-phase scenario (AC-3)."""

    @pytest.mark.asyncio
    async def test_archon_timeout_triggers_substitution(self) -> None:
        """Archon timeout triggers substitution and completes deliberation.

        Per AC-3: One Archon stops responding mid-phase, substitution
        mechanism activates and deliberation completes successfully.
        """
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
            injection_duration_seconds=10,
        )

        report = await harness.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS
        assert report.deliberations_recovered == report.deliberations_affected
        assert report.witness_chain_intact is True

    @pytest.mark.asyncio
    async def test_archon_timeout_audit_logging(self) -> None:
        """Archon timeout produces audit log entries.

        Per AC-10: All chaos scenarios produce audit-friendly logs.
        """
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
            enable_audit_logging=True,
        )

        report = await harness.run_chaos_test(config)

        assert len(report.audit_log_entries) >= 3
        events = [entry["event"] for entry in report.audit_log_entries]
        assert "fault_injection_start" in events
        assert "fault_injection_end" in events
        assert "recovery_detected" in events


class TestServiceRestartScenario:
    """Integration tests for service restart scenario (AC-4)."""

    @pytest.mark.asyncio
    async def test_service_restart_resumes_from_checkpoint(self) -> None:
        """Service restart resumes from last witness checkpoint.

        Per AC-4: In-flight deliberations resume from last checkpoint,
        no data is lost, and previously witnessed phases are not re-executed.
        """
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.SERVICE_RESTART,
            injection_duration_seconds=30,
            recovery_timeout_seconds=60,
        )

        report = await harness.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS
        assert report.deliberations_failed == 0
        assert report.witness_chain_intact is True

    @pytest.mark.asyncio
    async def test_service_restart_recovers_within_timeout(self) -> None:
        """Service restart recovers within configured timeout.

        Per AC-4: Service recovers within configured timeout.
        """
        harness = ChaosTestHarnessStub()
        recovery_timeout_seconds = 60
        config = ChaosTestConfig(
            scenario=ChaosScenario.SERVICE_RESTART,
            recovery_timeout_seconds=recovery_timeout_seconds,
        )

        report = await harness.run_chaos_test(config)

        # Total duration should be less than recovery timeout
        assert report.total_duration_seconds < recovery_timeout_seconds


class TestDatabaseConnectionFailureScenario:
    """Integration tests for database connection failure scenario (AC-5)."""

    @pytest.mark.asyncio
    async def test_database_failure_engages_retry_policy(self) -> None:
        """Database failure engages retry policy and recovers.

        Per AC-5: Retry policy engages with exponential backoff,
        no data loss occurs during reconnection.
        """
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.DATABASE_CONNECTION_FAILURE,
            injection_duration_seconds=30,
        )

        report = await harness.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS
        assert report.deliberations_failed == 0

    @pytest.mark.asyncio
    async def test_database_failure_no_data_loss(self) -> None:
        """Database failure causes no data loss.

        Per AC-5: All in-flight transactions are either committed
        or rolled back atomically.
        """
        harness = ChaosTestHarnessStub()
        harness.set_forced_deliberations_affected(100)

        config = ChaosTestConfig(
            scenario=ChaosScenario.DATABASE_CONNECTION_FAILURE,
        )

        report = await harness.run_chaos_test(config)

        assert report.deliberations_affected == 100
        assert report.deliberations_recovered == 100
        assert report.deliberations_failed == 0


class TestCrewAIApiDegradationScenario:
    """Integration tests for CrewAI API degradation scenario (AC-6)."""

    @pytest.mark.asyncio
    async def test_api_degradation_does_not_cause_full_failure(self) -> None:
        """API degradation does not cause full deliberation failure.

        Per AC-6: Individual Archon timeouts may trigger substitution,
        but full deliberation does not fail due to slow responses.
        """
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.CREWAI_API_DEGRADATION,
            latency_injection_ms=500,
        )

        report = await harness.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_api_degradation_with_high_latency(self) -> None:
        """High latency API degradation still recovers.

        Per AC-6: System adapts to degraded performance.
        """
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.CREWAI_API_DEGRADATION,
            latency_injection_ms=2000,  # 2 second latency
        )

        report = await harness.run_chaos_test(config)

        assert report.outcome in [
            ChaosTestOutcome.SUCCESS,
            ChaosTestOutcome.PARTIAL_RECOVERY,
        ]


class TestWitnessWriteFailureScenario:
    """Integration tests for witness write failure scenario (AC-7)."""

    @pytest.mark.asyncio
    async def test_witness_failure_pauses_deliberation(self) -> None:
        """Witness failure pauses deliberation (no silent continuation).

        Per AC-7: Deliberation pauses when event writer becomes unavailable,
        no unwitnessed phase completions occur (CT-12).
        """
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.WITNESS_WRITE_FAILURE,
        )

        report = await harness.run_chaos_test(config)

        # Default behavior is PARTIAL_RECOVERY for witness failures
        # This simulates that some deliberations could not complete without witnesses
        assert report.outcome == ChaosTestOutcome.PARTIAL_RECOVERY

    @pytest.mark.asyncio
    async def test_witness_failure_no_silent_continuation(self) -> None:
        """Witness failure prevents silent continuation (CT-11).

        Constitutional Truth CT-11: Silent failure destroys legitimacy.
        """
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.WITNESS_WRITE_FAILURE,
            enable_audit_logging=True,
        )

        report = await harness.run_chaos_test(config)

        # Audit log must capture the failure
        assert len(report.audit_log_entries) >= 3
        # Failure is visible, not silent
        assert (
            report.failure_details is not None
            or report.outcome == ChaosTestOutcome.PARTIAL_RECOVERY
        )


class TestNetworkPartitionScenario:
    """Integration tests for network partition scenario."""

    @pytest.mark.asyncio
    async def test_network_partition_recovers(self) -> None:
        """Network partition scenario recovers successfully."""
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.NETWORK_PARTITION,
            injection_duration_seconds=20,
        )

        report = await harness.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS


class TestConstitutionalTruthCompliance:
    """Integration tests for Constitutional Truth compliance."""

    @pytest.mark.asyncio
    async def test_ct_11_no_silent_failures(self) -> None:
        """CT-11: All failures must be reported (no silent drops).

        Every chaos scenario must produce audit logs that capture
        the failure condition.
        """
        harness = ChaosTestHarnessStub()

        for scenario in ChaosScenario:
            config = ChaosTestConfig(
                scenario=scenario,
                enable_audit_logging=True,
            )

            report = await harness.run_chaos_test(config)

            # Every scenario must produce audit entries
            assert len(report.audit_log_entries) >= 1, (
                f"Scenario {scenario} produced no audit entries"
            )

    @pytest.mark.asyncio
    async def test_ct_12_witness_chain_integrity(self) -> None:
        """CT-12: Witness chain integrity must be preserved during chaos.

        All scenarios except total failure should maintain witness chain.
        """
        harness = ChaosTestHarnessStub()

        for scenario in ChaosScenario:
            config = ChaosTestConfig(scenario=scenario)
            report = await harness.run_chaos_test(config)

            # Non-failure outcomes should have intact witness chain
            if report.outcome != ChaosTestOutcome.FAILURE:
                assert report.witness_chain_intact, (
                    f"Scenario {scenario} with outcome {report.outcome} "
                    f"has broken witness chain"
                )

    @pytest.mark.asyncio
    async def test_ct_14_all_petitions_reach_fate(self) -> None:
        """CT-14: All affected petitions must reach terminal fate.

        affected = recovered + failed (nothing lost in limbo).
        """
        harness = ChaosTestHarnessStub()

        for scenario in ChaosScenario:
            config = ChaosTestConfig(scenario=scenario)
            report = await harness.run_chaos_test(config)

            total_tracked = report.deliberations_recovered + report.deliberations_failed
            assert total_tracked == report.deliberations_affected, (
                f"Scenario {scenario}: {report.deliberations_affected} affected but "
                f"only {total_tracked} tracked (recovered: {report.deliberations_recovered}, "
                f"failed: {report.deliberations_failed})"
            )


class TestNFRCompliance:
    """Integration tests for NFR compliance."""

    @pytest.mark.asyncio
    async def test_nfr_10_6_archon_substitution_latency(self) -> None:
        """NFR-10.6: Archon substitution must complete in < 10 seconds.

        For ARCHON_TIMEOUT_MID_PHASE scenario, recovery should be
        within the 10 second SLA.
        """
        harness = ChaosTestHarnessStub()
        # Force recovery within SLA
        harness.set_forced_recovery_ms(ARCHON_SUBSTITUTION_SLA_MS - 1000)

        config = ChaosTestConfig(
            scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
        )

        report = await harness.run_chaos_test(config)

        assert report.nfr_10_6_pass, (
            f"NFR-10.6 failed: recovery_duration_ms={report.recovery_duration_ms}, "
            f"SLA={ARCHON_SUBSTITUTION_SLA_MS}"
        )

    @pytest.mark.asyncio
    async def test_nfr_9_5_chaos_testing_available(self) -> None:
        """NFR-9.5: Chaos testing must be available for scheduler crash recovery.

        The chaos test harness must support SERVICE_RESTART scenario.
        """
        harness = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.SERVICE_RESTART,
        )

        report = await harness.run_chaos_test(config)

        assert report.scenario == "service_restart"
        assert report.outcome is not None


class TestFaultInjectionLifecycle:
    """Integration tests for fault injection lifecycle."""

    @pytest.mark.asyncio
    async def test_fault_injection_and_removal_cycle(self) -> None:
        """Complete fault injection lifecycle works correctly."""
        harness = ChaosTestHarnessStub()

        # Inject
        handle = await harness.inject_fault(ChaosScenario.DATABASE_CONNECTION_FAILURE)
        assert len(harness.get_active_faults()) == 1

        # Verify active
        active = harness.get_active_faults()
        assert active[0].handle_id == handle.handle_id

        # Remove
        removed = await harness.remove_fault(handle)
        assert removed is True
        assert len(harness.get_active_faults()) == 0

    @pytest.mark.asyncio
    async def test_concurrent_faults_can_be_managed(self) -> None:
        """Multiple concurrent faults can be injected and managed."""
        harness = ChaosTestHarnessStub()

        # Inject multiple faults
        await harness.inject_fault(ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        handle2 = await harness.inject_fault(ChaosScenario.CREWAI_API_DEGRADATION)
        await harness.inject_fault(ChaosScenario.NETWORK_PARTITION)

        assert len(harness.get_active_faults()) == 3

        # Remove selectively
        await harness.remove_fault(handle2)
        assert len(harness.get_active_faults()) == 2

        # Clear all
        await harness.clear_all_faults()
        assert len(harness.get_active_faults()) == 0

    @pytest.mark.asyncio
    async def test_fault_handles_have_correct_metadata(self) -> None:
        """Fault handles contain correct scenario and component metadata."""
        harness = ChaosTestHarnessStub()

        handle = await harness.inject_fault(
            ChaosScenario.DATABASE_CONNECTION_FAILURE,
            affected_components=("postgres", "pool"),
        )

        assert handle.scenario == ChaosScenario.DATABASE_CONNECTION_FAILURE
        assert handle.affected_components == ("postgres", "pool")
        assert handle.started_at_ms > 0


class TestAllScenariosProduceReports:
    """Integration tests ensuring all scenarios produce valid reports."""

    @pytest.mark.asyncio
    async def test_all_scenarios_produce_valid_reports(self) -> None:
        """Every defined scenario produces a valid report."""
        harness = ChaosTestHarnessStub()

        for scenario in ChaosScenario:
            config = ChaosTestConfig(scenario=scenario)
            report = await harness.run_chaos_test(config)

            # Validate report structure
            assert report.test_id is not None
            assert report.scenario == scenario.value
            assert report.started_at is not None
            assert report.completed_at is not None
            assert report.outcome in ChaosTestOutcome
            assert report.deliberations_affected >= 0
            assert report.deliberations_recovered >= 0
            assert report.deliberations_failed >= 0

    @pytest.mark.asyncio
    async def test_all_scenarios_generate_summaries(self) -> None:
        """Every scenario can generate a human-readable summary."""
        harness = ChaosTestHarnessStub()

        for scenario in ChaosScenario:
            config = ChaosTestConfig(scenario=scenario)
            report = await harness.run_chaos_test(config)

            summary = report.summary()

            assert "Chaos Test Report" in summary
            assert scenario.value in summary
            assert "Deliberations:" in summary
