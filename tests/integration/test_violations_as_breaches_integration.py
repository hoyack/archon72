"""Integration tests for Violations as Constitutional Breaches (Story 9.6, FR109).

Tests end-to-end flow from violation detection to breach creation,
including integration with existing breach and escalation infrastructure.

Constitutional Constraints:
- FR109: Emergence violations create constitutional breaches
- FR55: No emergence claims (the violated requirement)
- FR31: 7-day escalation timer starts automatically
- CT-11: HALT CHECK FIRST
- CT-12: All events witnessed
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Optional
from uuid import UUID, uuid4

import pytest

from src.application.ports.prohibited_language_scanner import ScanResult
from src.application.services.emergence_violation_breach_service import (
    EMERGENCE_VIOLATED_REQUIREMENT,
    EmergenceViolationBreachService,
)
from src.application.services.emergence_violation_orchestrator import (
    EmergenceViolationOrchestrator,
)
from src.domain.errors.prohibited_language import ProhibitedLanguageBlockedError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import (
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)
from src.infrastructure.stubs.emergence_violation_breach_service_stub import (
    EmergenceViolationBreachServiceStub,
)


# =============================================================================
# Test Doubles (Inline for integration test isolation)
# =============================================================================


class InMemoryBreachDeclarationService:
    """In-memory breach declaration service for integration tests."""

    def __init__(self) -> None:
        self._breaches: list[BreachEventPayload] = []
        self._halted: bool = False
        self._halt_reason: str = "Test halt"

    def set_halted(self, halted: bool, reason: str = "Test halt") -> None:
        """Set halt state."""
        self._halted = halted
        self._halt_reason = reason

    def get_all_breaches(self) -> list[BreachEventPayload]:
        """Get all declared breaches."""
        return list(self._breaches)

    def clear(self) -> None:
        """Clear all state."""
        self._breaches.clear()
        self._halted = False
        self._halt_reason = "Test halt"

    async def declare_breach(
        self,
        breach_type: BreachType,
        violated_requirement: str,
        severity: BreachSeverity,
        details: dict[str, Any],
        source_event_id: Optional[UUID] = None,
    ) -> BreachEventPayload:
        """Declare a breach (simulates full service)."""
        if self._halted:
            raise SystemHaltedError(f"CT-11: System is halted: {self._halt_reason}")

        breach = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=breach_type,
            violated_requirement=violated_requirement,
            severity=severity,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType(details),
            source_event_id=source_event_id,
        )
        self._breaches.append(breach)
        return breach


class InMemoryHaltChecker:
    """In-memory halt checker for integration tests."""

    def __init__(self) -> None:
        self._halted: bool = False
        self._halt_reason: str = "Test halt"

    def set_halted(self, halted: bool, reason: str = "Test halt") -> None:
        """Set halt state."""
        self._halted = halted
        self._halt_reason = reason

    async def is_halted(self) -> bool:
        """Check if halted."""
        return self._halted

    async def get_halt_reason(self) -> str:
        """Get halt reason."""
        return self._halt_reason


class InMemoryBlockingService:
    """In-memory blocking service for integration tests."""

    def __init__(self) -> None:
        self._prohibited_terms: tuple[str, ...] = (
            "emergence",
            "consciousness",
            "sentience",
            "self-aware",
            "awakened",
        )
        self._halted: bool = False
        self._halt_reason: str = "Test halt"
        self._blocked_events: list[dict[str, Any]] = []

    def set_halted(self, halted: bool, reason: str = "Test halt") -> None:
        """Set halt state."""
        self._halted = halted
        self._halt_reason = reason

    def get_blocked_events(self) -> list[dict[str, Any]]:
        """Get all blocked events."""
        return list(self._blocked_events)

    def clear(self) -> None:
        """Clear all state."""
        self._blocked_events.clear()
        self._halted = False

    async def check_content_for_prohibited_language(
        self,
        content_id: str,
        content: str,
    ) -> ScanResult:
        """Check content for prohibited language."""
        if self._halted:
            raise SystemHaltedError(f"CT-11: System is halted: {self._halt_reason}")

        # Check for prohibited terms (case-insensitive)
        content_lower = content.lower()
        matched = tuple(
            term for term in self._prohibited_terms if term in content_lower
        )

        if matched:
            # Record the blocking event
            self._blocked_events.append(
                {
                    "content_id": content_id,
                    "matched_terms": matched,
                    "blocked_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            raise ProhibitedLanguageBlockedError(
                content_id=content_id,
                matched_terms=matched,
            )

        return ScanResult(
            violations_found=False,
            matched_terms=(),
            detection_method="keyword_scan",
        )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def halt_checker() -> InMemoryHaltChecker:
    """Provide halt checker."""
    return InMemoryHaltChecker()


@pytest.fixture
def breach_declaration_service() -> InMemoryBreachDeclarationService:
    """Provide breach declaration service."""
    return InMemoryBreachDeclarationService()


@pytest.fixture
def blocking_service() -> InMemoryBlockingService:
    """Provide blocking service."""
    return InMemoryBlockingService()


@pytest.fixture
def emergence_breach_service(
    breach_declaration_service: InMemoryBreachDeclarationService,
    halt_checker: InMemoryHaltChecker,
) -> EmergenceViolationBreachService:
    """Provide emergence violation breach service."""
    return EmergenceViolationBreachService(
        breach_service=breach_declaration_service,  # type: ignore[arg-type]
        halt_checker=halt_checker,
    )


@pytest.fixture
def breach_service_stub() -> EmergenceViolationBreachServiceStub:
    """Provide breach service stub."""
    return EmergenceViolationBreachServiceStub()


@pytest.fixture
def orchestrator(
    blocking_service: InMemoryBlockingService,
    breach_service_stub: EmergenceViolationBreachServiceStub,
    halt_checker: InMemoryHaltChecker,
) -> EmergenceViolationOrchestrator:
    """Provide orchestrator with stub breach service."""
    return EmergenceViolationOrchestrator(
        blocking_service=blocking_service,  # type: ignore[arg-type]
        breach_service=breach_service_stub,  # type: ignore[arg-type]
        halt_checker=halt_checker,
    )


# =============================================================================
# End-to-End Tests: Violation to Breach
# =============================================================================


class TestEndToEndViolationToBreach:
    """End-to-end tests for violation detection to breach creation."""

    @pytest.mark.asyncio
    async def test_violation_creates_breach(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Detected violation results in breach creation (FR109)."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="e2e-test-1",
                content="This system has achieved emergence.",
            )

        breaches = breach_service_stub.get_created_breaches()
        assert len(breaches) == 1
        assert breaches[0].breach_type == BreachType.EMERGENCE_VIOLATION

    @pytest.mark.asyncio
    async def test_clean_content_no_breach(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Clean content does not create breach."""
        result = await orchestrator.check_and_report_violation(
            content_id="e2e-test-2",
            content="This is perfectly safe content about normal operations.",
        )

        assert result.violations_found is False
        breaches = breach_service_stub.get_created_breaches()
        assert len(breaches) == 0

    @pytest.mark.asyncio
    async def test_multiple_violations_multiple_breaches(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Each violation creates a separate breach."""
        # First violation
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="e2e-test-3a",
                content="System shows emergence.",
            )

        # Second violation
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="e2e-test-3b",
                content="AI has consciousness.",
            )

        breaches = breach_service_stub.get_created_breaches()
        assert len(breaches) == 2

    @pytest.mark.asyncio
    async def test_breach_details_match_violation(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Breach details match the violation that triggered it."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="detail-match-test",
                content="The system is self-aware and has consciousness.",
            )

        breaches = breach_service_stub.get_created_breaches()
        assert len(breaches) == 1

        breach = breaches[0]
        details = dict(breach.details)
        assert details["content_id"] == "detail-match-test"
        # Matched terms should include what was found
        matched = details["matched_terms"]
        assert "consciousness" in matched or "self-aware" in matched


# =============================================================================
# Breach Type Tests
# =============================================================================


class TestBreachType:
    """Tests for correct breach type assignment."""

    @pytest.mark.asyncio
    async def test_breach_type_is_emergence_violation(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Breach type is EMERGENCE_VIOLATION (FR109)."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="type-test-1",
                content="This is emergence.",
            )

        breaches = breach_service_stub.get_created_breaches()
        assert breaches[0].breach_type == BreachType.EMERGENCE_VIOLATION

    @pytest.mark.asyncio
    async def test_violated_requirement_is_fr55(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Violated requirement is FR55 (no emergence claims)."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="type-test-2",
                content="Sentience detected.",
            )

        breaches = breach_service_stub.get_created_breaches()
        assert breaches[0].violated_requirement == "FR55"


# =============================================================================
# HALT CHECK FIRST Integration Tests (CT-11)
# =============================================================================


class TestHaltCheckIntegration:
    """Integration tests for HALT CHECK FIRST across all services."""

    @pytest.mark.asyncio
    async def test_orchestrator_halt_blocks_all(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        halt_checker: InMemoryHaltChecker,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Orchestrator halt check prevents all operations (CT-11)."""
        halt_checker.set_halted(True, "Fork detected in event store")

        with pytest.raises(SystemHaltedError) as exc_info:
            await orchestrator.check_and_report_violation(
                content_id="halt-test-1",
                content="emergence",
            )

        assert "CT-11" in str(exc_info.value)
        # No breaches should be created
        assert len(breach_service_stub.get_created_breaches()) == 0

    @pytest.mark.asyncio
    async def test_breach_service_halt_check(
        self,
        emergence_breach_service: EmergenceViolationBreachService,
        halt_checker: InMemoryHaltChecker,
    ) -> None:
        """Breach service halt check prevents breach creation (CT-11)."""
        halt_checker.set_halted(True, "Hash chain corruption")

        with pytest.raises(SystemHaltedError) as exc_info:
            await emergence_breach_service.create_breach_for_violation(
                violation_event_id=uuid4(),
                content_id="halt-test-2",
                matched_terms=("emergence",),
                detection_method="keyword_scan",
            )

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_blocking_service_halt_check(
        self,
        blocking_service: InMemoryBlockingService,
    ) -> None:
        """Blocking service halt check prevents scanning (CT-11)."""
        blocking_service.set_halted(True, "Integrity failure")

        with pytest.raises(SystemHaltedError):
            await blocking_service.check_content_for_prohibited_language(
                content_id="halt-test-3",
                content="emergence",
            )

    @pytest.mark.asyncio
    async def test_services_resume_after_halt_cleared(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        halt_checker: InMemoryHaltChecker,
    ) -> None:
        """Services resume normal operation after halt is cleared."""
        # Start halted
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await orchestrator.check_and_report_violation(
                content_id="resume-test",
                content="emergence",
            )

        # Clear halt
        halt_checker.set_halted(False)

        # Should work now (and trigger violation)
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="resume-test",
                content="emergence",
            )


# =============================================================================
# Breach Event Witnessing Tests (CT-12)
# =============================================================================


class TestBreachWitnessing:
    """Tests for breach event witnessing (CT-12)."""

    @pytest.mark.asyncio
    async def test_breach_has_detection_timestamp(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Breach event has detection timestamp for audit trail (CT-12)."""
        before = datetime.now(timezone.utc)

        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="witness-test-1",
                content="emergence",
            )

        after = datetime.now(timezone.utc)

        breaches = breach_service_stub.get_created_breaches()
        assert len(breaches) == 1

        timestamp = breaches[0].detection_timestamp
        assert before <= timestamp <= after

    @pytest.mark.asyncio
    async def test_breach_has_unique_id(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Each breach has a unique ID (CT-12 - witnessing)."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="witness-test-2a",
                content="emergence",
            )

        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="witness-test-2b",
                content="consciousness",
            )

        breaches = breach_service_stub.get_created_breaches()
        assert len(breaches) == 2
        assert breaches[0].breach_id != breaches[1].breach_id


# =============================================================================
# Escalation Timer Tests (FR31)
# =============================================================================


class TestEscalationTimer:
    """Tests for 7-day escalation timer integration (FR31).

    Note: The actual escalation logic is in EscalationService.
    These tests verify that breaches are created in a way that
    makes them eligible for the 7-day escalation process.
    """

    @pytest.mark.asyncio
    async def test_breach_has_timestamp_for_escalation(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Breach has detection_timestamp needed for escalation (FR31)."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="escalation-test-1",
                content="emergence",
            )

        breaches = breach_service_stub.get_created_breaches()
        assert len(breaches) == 1

        # Detection timestamp is required for escalation calculation
        assert breaches[0].detection_timestamp is not None
        assert isinstance(breaches[0].detection_timestamp, datetime)

    @pytest.mark.asyncio
    async def test_breach_has_id_for_acknowledgment(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Breach has breach_id needed for acknowledgment (FR31)."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="escalation-test-2",
                content="consciousness",
            )

        breaches = breach_service_stub.get_created_breaches()
        assert len(breaches) == 1

        # Breach ID is required for acknowledgment
        assert breaches[0].breach_id is not None
        assert isinstance(breaches[0].breach_id, UUID)


# =============================================================================
# Service Stub Tests
# =============================================================================


class TestServiceStub:
    """Tests for EmergenceViolationBreachServiceStub."""

    @pytest.mark.asyncio
    async def test_stub_creates_breach(
        self,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Stub creates breach correctly."""
        breach = await breach_service_stub.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="stub-test-1",
            matched_terms=("emergence",),
            detection_method="keyword_scan",
        )

        assert breach.breach_type == BreachType.EMERGENCE_VIOLATION
        assert breach.violated_requirement == "FR55"
        assert breach.severity == BreachSeverity.HIGH

    @pytest.mark.asyncio
    async def test_stub_halt_check(
        self,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Stub respects halt state."""
        breach_service_stub.set_halt_state(True, "Test halt")

        with pytest.raises(SystemHaltedError):
            await breach_service_stub.create_breach_for_violation(
                violation_event_id=uuid4(),
                content_id="stub-test-2",
                matched_terms=("emergence",),
                detection_method="keyword_scan",
            )

    @pytest.mark.asyncio
    async def test_stub_clear(
        self,
        breach_service_stub: EmergenceViolationBreachServiceStub,
    ) -> None:
        """Stub clear works correctly."""
        await breach_service_stub.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="stub-test-3",
            matched_terms=("emergence",),
            detection_method="keyword_scan",
        )

        assert len(breach_service_stub.get_created_breaches()) == 1

        breach_service_stub.clear()

        assert len(breach_service_stub.get_created_breaches()) == 0
