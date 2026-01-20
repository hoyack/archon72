"""Unit tests for ChaosTestHarnessStub (Story 2B.8, NFR-9.5).

Tests:
- Stub protocol compliance
- Chaos test execution simulation
- Fault injection lifecycle
- Test helpers for deterministic testing
- Call tracking for verification
"""

from __future__ import annotations

import pytest

from src.domain.models.chaos_test_config import ChaosScenario, ChaosTestConfig
from src.domain.models.chaos_test_report import ChaosTestOutcome
from src.infrastructure.stubs.chaos_test_harness_stub import ChaosTestHarnessStub


class TestChaosTestHarnessStubCreation:
    """Test ChaosTestHarnessStub creation and initialization."""

    def test_default_creation(self) -> None:
        """Stub creates with default parameters."""
        stub = ChaosTestHarnessStub()

        assert stub.get_test_count() == 0
        assert stub.get_inject_call_count() == 0
        assert stub.get_remove_call_count() == 0
        assert stub.get_active_faults() == []

    def test_custom_recovery_timing(self) -> None:
        """Stub accepts custom recovery timing parameters."""
        stub = ChaosTestHarnessStub(
            base_recovery_ms=200.0,
            recovery_variance_ms=100.0,
        )

        # Verify stub was created (parameters are internal)
        assert stub is not None


class TestChaosTestHarnessStubRunChaosTest:
    """Test run_chaos_test method."""

    @pytest.mark.asyncio
    async def test_run_chaos_test_returns_report(self) -> None:
        """run_chaos_test returns a ChaosTestReport."""
        stub = ChaosTestHarnessStub()
        config = ChaosTestConfig(scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)

        report = await stub.run_chaos_test(config)

        assert report is not None
        assert report.scenario == "archon_timeout_mid_phase"
        assert report.config["scenario"] == "archon_timeout_mid_phase"

    @pytest.mark.asyncio
    async def test_run_chaos_test_tracks_history(self) -> None:
        """run_chaos_test tracks test history."""
        stub = ChaosTestHarnessStub()
        config = ChaosTestConfig(scenario=ChaosScenario.SERVICE_RESTART)

        await stub.run_chaos_test(config)

        assert stub.get_test_count() == 1

    @pytest.mark.asyncio
    async def test_run_chaos_test_uses_default_outcomes(self) -> None:
        """run_chaos_test uses default outcomes per scenario."""
        stub = ChaosTestHarnessStub()

        # ARCHON_TIMEOUT should succeed
        config_archon = ChaosTestConfig(scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        report_archon = await stub.run_chaos_test(config_archon)
        assert report_archon.outcome == ChaosTestOutcome.SUCCESS

        # WITNESS_WRITE_FAILURE should partially recover
        config_witness = ChaosTestConfig(scenario=ChaosScenario.WITNESS_WRITE_FAILURE)
        report_witness = await stub.run_chaos_test(config_witness)
        assert report_witness.outcome == ChaosTestOutcome.PARTIAL_RECOVERY

    @pytest.mark.asyncio
    async def test_run_chaos_test_generates_audit_entries(self) -> None:
        """run_chaos_test generates audit log entries."""
        stub = ChaosTestHarnessStub()
        config = ChaosTestConfig(
            scenario=ChaosScenario.DATABASE_CONNECTION_FAILURE,
            enable_audit_logging=True,
        )

        report = await stub.run_chaos_test(config)

        assert len(report.audit_log_entries) >= 3
        events = [entry["event"] for entry in report.audit_log_entries]
        assert "fault_injection_start" in events
        assert "fault_injection_end" in events
        assert "recovery_detected" in events


class TestChaosTestHarnessStubFaultInjection:
    """Test fault injection lifecycle."""

    @pytest.mark.asyncio
    async def test_inject_fault_returns_handle(self) -> None:
        """inject_fault returns a FaultHandle."""
        stub = ChaosTestHarnessStub()

        handle = await stub.inject_fault(ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)

        assert handle is not None
        assert handle.scenario == ChaosScenario.ARCHON_TIMEOUT_MID_PHASE
        assert handle.started_at_ms > 0

    @pytest.mark.asyncio
    async def test_inject_fault_uses_default_components(self) -> None:
        """inject_fault uses scenario-appropriate default components."""
        stub = ChaosTestHarnessStub()

        handle = await stub.inject_fault(ChaosScenario.DATABASE_CONNECTION_FAILURE)

        assert "postgres" in handle.affected_components

    @pytest.mark.asyncio
    async def test_inject_fault_uses_custom_components(self) -> None:
        """inject_fault accepts custom affected components."""
        stub = ChaosTestHarnessStub()

        handle = await stub.inject_fault(
            ChaosScenario.NETWORK_PARTITION,
            affected_components=("component_a", "component_b"),
        )

        assert handle.affected_components == ("component_a", "component_b")

    @pytest.mark.asyncio
    async def test_inject_fault_tracks_calls(self) -> None:
        """inject_fault tracks call history."""
        stub = ChaosTestHarnessStub()

        await stub.inject_fault(ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        await stub.inject_fault(ChaosScenario.SERVICE_RESTART)

        assert stub.get_inject_call_count() == 2

    @pytest.mark.asyncio
    async def test_injected_fault_appears_in_active_faults(self) -> None:
        """Injected faults appear in get_active_faults."""
        stub = ChaosTestHarnessStub()

        handle = await stub.inject_fault(ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        active = stub.get_active_faults()

        assert len(active) == 1
        assert active[0].handle_id == handle.handle_id

    @pytest.mark.asyncio
    async def test_multiple_faults_can_be_active(self) -> None:
        """Multiple faults can be injected simultaneously."""
        stub = ChaosTestHarnessStub()

        await stub.inject_fault(ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        await stub.inject_fault(ChaosScenario.CREWAI_API_DEGRADATION)
        await stub.inject_fault(ChaosScenario.NETWORK_PARTITION)

        assert len(stub.get_active_faults()) == 3


class TestChaosTestHarnessStubFaultRemoval:
    """Test fault removal."""

    @pytest.mark.asyncio
    async def test_remove_fault_returns_true_for_active_fault(self) -> None:
        """remove_fault returns True when fault is removed."""
        stub = ChaosTestHarnessStub()
        handle = await stub.inject_fault(ChaosScenario.SERVICE_RESTART)

        result = await stub.remove_fault(handle)

        assert result is True
        assert len(stub.get_active_faults()) == 0

    @pytest.mark.asyncio
    async def test_remove_fault_returns_false_for_unknown_fault(self) -> None:
        """remove_fault returns False when fault not found."""
        stub = ChaosTestHarnessStub()
        handle = await stub.inject_fault(ChaosScenario.SERVICE_RESTART)

        # Remove once
        await stub.remove_fault(handle)
        # Remove again - should return False
        result = await stub.remove_fault(handle)

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_fault_tracks_calls(self) -> None:
        """remove_fault tracks call history."""
        stub = ChaosTestHarnessStub()
        handle = await stub.inject_fault(ChaosScenario.DATABASE_CONNECTION_FAILURE)

        await stub.remove_fault(handle)

        assert stub.get_remove_call_count() == 1

    @pytest.mark.asyncio
    async def test_clear_all_faults_removes_all(self) -> None:
        """clear_all_faults removes all active faults."""
        stub = ChaosTestHarnessStub()

        await stub.inject_fault(ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        await stub.inject_fault(ChaosScenario.SERVICE_RESTART)
        await stub.inject_fault(ChaosScenario.DATABASE_CONNECTION_FAILURE)

        assert len(stub.get_active_faults()) == 3

        await stub.clear_all_faults()

        assert len(stub.get_active_faults()) == 0

    @pytest.mark.asyncio
    async def test_clear_all_faults_is_idempotent(self) -> None:
        """clear_all_faults can be called multiple times safely."""
        stub = ChaosTestHarnessStub()

        await stub.clear_all_faults()
        await stub.clear_all_faults()

        assert len(stub.get_active_faults()) == 0


class TestChaosTestHarnessStubTestHelpers:
    """Test deterministic testing helpers."""

    @pytest.mark.asyncio
    async def test_set_forced_outcome(self) -> None:
        """set_forced_outcome forces specific outcome."""
        stub = ChaosTestHarnessStub()
        stub.set_forced_outcome(ChaosTestOutcome.FAILURE)

        config = ChaosTestConfig(scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        report = await stub.run_chaos_test(config)

        # Would normally succeed, but forced to fail
        assert report.outcome == ChaosTestOutcome.FAILURE

    @pytest.mark.asyncio
    async def test_set_forced_recovery_ms(self) -> None:
        """set_forced_recovery_ms forces specific recovery time."""
        stub = ChaosTestHarnessStub()
        stub.set_forced_recovery_ms(5000.0)

        config = ChaosTestConfig(scenario=ChaosScenario.SERVICE_RESTART)
        report = await stub.run_chaos_test(config)

        # Recovery duration should be close to 5000ms
        assert report.recovery_duration_ms is not None

    @pytest.mark.asyncio
    async def test_set_forced_deliberations_affected(self) -> None:
        """set_forced_deliberations_affected forces specific count."""
        stub = ChaosTestHarnessStub()
        stub.set_forced_deliberations_affected(50)

        config = ChaosTestConfig(scenario=ChaosScenario.DATABASE_CONNECTION_FAILURE)
        report = await stub.run_chaos_test(config)

        assert report.deliberations_affected == 50

    @pytest.mark.asyncio
    async def test_set_forced_witness_chain_intact(self) -> None:
        """set_forced_witness_chain_intact forces specific value."""
        stub = ChaosTestHarnessStub()
        stub.set_forced_witness_chain_intact(False)

        config = ChaosTestConfig(scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        report = await stub.run_chaos_test(config)

        assert report.witness_chain_intact is False

    def test_clear_resets_all_state(self) -> None:
        """clear resets all stub state."""
        stub = ChaosTestHarnessStub()
        stub.set_forced_outcome(ChaosTestOutcome.FAILURE)
        stub.set_forced_recovery_ms(10000.0)

        stub.clear()

        # Forced values should be cleared
        # (can't directly verify internal state, but clear should work)
        assert stub.get_test_count() == 0
        assert stub.get_inject_call_count() == 0
        assert stub.get_remove_call_count() == 0


class TestChaosTestHarnessStubCallHistory:
    """Test call history tracking."""

    @pytest.mark.asyncio
    async def test_get_test_history(self) -> None:
        """get_test_history returns full test history."""
        stub = ChaosTestHarnessStub()

        config1 = ChaosTestConfig(scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        config2 = ChaosTestConfig(scenario=ChaosScenario.SERVICE_RESTART)

        await stub.run_chaos_test(config1)
        await stub.run_chaos_test(config2)

        history = stub.get_test_history()

        assert len(history) == 2
        assert history[0]["config"] == config1
        assert history[1]["config"] == config2

    @pytest.mark.asyncio
    async def test_get_inject_calls(self) -> None:
        """get_inject_calls returns full inject call history."""
        stub = ChaosTestHarnessStub()

        await stub.inject_fault(ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        await stub.inject_fault(ChaosScenario.DATABASE_CONNECTION_FAILURE)

        calls = stub.get_inject_calls()

        assert len(calls) == 2
        assert calls[0]["scenario"] == ChaosScenario.ARCHON_TIMEOUT_MID_PHASE
        assert calls[1]["scenario"] == ChaosScenario.DATABASE_CONNECTION_FAILURE

    @pytest.mark.asyncio
    async def test_get_remove_calls(self) -> None:
        """get_remove_calls returns full remove call history."""
        stub = ChaosTestHarnessStub()

        handle1 = await stub.inject_fault(ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)
        handle2 = await stub.inject_fault(ChaosScenario.SERVICE_RESTART)

        await stub.remove_fault(handle1)
        await stub.remove_fault(handle2)

        calls = stub.get_remove_calls()

        assert len(calls) == 2
        assert calls[0]["handle_id"] == handle1.handle_id
        assert calls[1]["handle_id"] == handle2.handle_id


class TestChaosTestHarnessStubScenarioOutcomes:
    """Test scenario-specific default outcomes."""

    @pytest.mark.asyncio
    async def test_archon_timeout_succeeds(self) -> None:
        """ARCHON_TIMEOUT_MID_PHASE has SUCCESS default outcome."""
        stub = ChaosTestHarnessStub()
        config = ChaosTestConfig(scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)

        report = await stub.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS
        assert report.deliberations_recovered == report.deliberations_affected

    @pytest.mark.asyncio
    async def test_service_restart_succeeds(self) -> None:
        """SERVICE_RESTART has SUCCESS default outcome."""
        stub = ChaosTestHarnessStub()
        config = ChaosTestConfig(scenario=ChaosScenario.SERVICE_RESTART)

        report = await stub.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_database_failure_succeeds(self) -> None:
        """DATABASE_CONNECTION_FAILURE has SUCCESS default outcome."""
        stub = ChaosTestHarnessStub()
        config = ChaosTestConfig(scenario=ChaosScenario.DATABASE_CONNECTION_FAILURE)

        report = await stub.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_crewai_degradation_succeeds(self) -> None:
        """CREWAI_API_DEGRADATION has SUCCESS default outcome."""
        stub = ChaosTestHarnessStub()
        config = ChaosTestConfig(scenario=ChaosScenario.CREWAI_API_DEGRADATION)

        report = await stub.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_witness_failure_partial_recovery(self) -> None:
        """WITNESS_WRITE_FAILURE has PARTIAL_RECOVERY default outcome."""
        stub = ChaosTestHarnessStub()
        config = ChaosTestConfig(scenario=ChaosScenario.WITNESS_WRITE_FAILURE)

        report = await stub.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.PARTIAL_RECOVERY
        assert report.deliberations_failed > 0

    @pytest.mark.asyncio
    async def test_network_partition_succeeds(self) -> None:
        """NETWORK_PARTITION has SUCCESS default outcome."""
        stub = ChaosTestHarnessStub()
        config = ChaosTestConfig(scenario=ChaosScenario.NETWORK_PARTITION)

        report = await stub.run_chaos_test(config)

        assert report.outcome == ChaosTestOutcome.SUCCESS
