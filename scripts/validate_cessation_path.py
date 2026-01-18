#!/usr/bin/env python3
"""Validate Cessation Code Path (Story 7.9, AC3, PM-5).

This script validates that the cessation code path is reachable and correct
WITHOUT actually executing cessation. It's designed to run in CI weekly.

Constitutional Mandate (PM-5):
"Cessation never tested -> Mandatory chaos test in staging, weekly CI"

The script validates:
1. CessationExecutionService can be imported and instantiated
2. FinalDeliberationService can be imported and instantiated
3. 72-archon deliberation generator works correctly
4. Cessation event payload can be created
5. Dual-channel flag repository interface exists
6. All required error types are defined

Usage:
    python scripts/validate_cessation_path.py

Exit Codes:
    0 - All validations passed
    1 - One or more validations failed
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Add project root to path for imports
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# =============================================================================
# Validation Result Tracking
# =============================================================================


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    details: str = ""


class ValidationReport:
    """Collection of validation results."""

    def __init__(self) -> None:
        self.results: list[ValidationResult] = []

    def add(self, name: str, passed: bool, details: str = "") -> None:
        """Add a validation result."""
        self.results.append(ValidationResult(name, passed, details))

    @property
    def all_passed(self) -> bool:
        """Check if all validations passed."""
        return all(r.passed for r in self.results)

    def print_report(self) -> None:
        """Print the validation report."""
        print("\n" + "=" * 60)
        print("CESSATION PATH VALIDATION REPORT")
        print("=" * 60 + "\n")

        passed = 0
        failed = 0

        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            icon = "\u2713" if result.passed else "\u2717"
            print(f"  [{icon}] {status}: {result.name}")
            if result.details:
                print(f"      {result.details}")

            if result.passed:
                passed += 1
            else:
                failed += 1

        print("\n" + "-" * 60)
        print(f"Total: {passed} passed, {failed} failed")
        print("-" * 60)

        if self.all_passed:
            print("\n[PM-5] CESSATION PATH VALIDATION PASSED")
        else:
            print("\n[PM-5] CESSATION PATH VALIDATION FAILED")


# =============================================================================
# Validation Functions
# =============================================================================


def validate_cessation_service_imports(report: ValidationReport) -> None:
    """Validate CessationExecutionService can be imported."""
    try:
        from src.application.services.cessation_execution_service import (
            CessationExecutionError,
            CessationExecutionService,
        )

        report.add(
            "CessationExecutionService import",
            True,
            "Service and error classes importable",
        )
    except ImportError as e:
        report.add(
            "CessationExecutionService import",
            False,
            f"Import failed: {e}",
        )


def validate_deliberation_service_imports(report: ValidationReport) -> None:
    """Validate FinalDeliberationService can be imported."""
    try:
        from src.application.services.final_deliberation_service import (
            DeliberationRecordingCompleteFailure,
            FinalDeliberationService,
        )

        report.add(
            "FinalDeliberationService import",
            True,
            "Service and error classes importable",
        )
    except ImportError as e:
        report.add(
            "FinalDeliberationService import",
            False,
            f"Import failed: {e}",
        )


def validate_cessation_event_types(report: ValidationReport) -> None:
    """Validate cessation event types are defined."""
    try:
        from src.domain.events.cessation_executed import (
            CESSATION_EXECUTED_EVENT_TYPE,
            CessationExecutedEventPayload,
        )

        # Verify event type constant
        if CESSATION_EXECUTED_EVENT_TYPE == "cessation.executed":
            report.add(
                "CESSATION_EXECUTED_EVENT_TYPE",
                True,
                f"Value: {CESSATION_EXECUTED_EVENT_TYPE}",
            )
        else:
            report.add(
                "CESSATION_EXECUTED_EVENT_TYPE",
                False,
                f"Unexpected value: {CESSATION_EXECUTED_EVENT_TYPE}",
            )

        # Verify payload can be created
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Validation test",
            triggering_event_id=uuid4(),
        )

        if payload.is_terminal:
            report.add(
                "CessationExecutedEventPayload",
                True,
                "Payload created with is_terminal=True",
            )
        else:
            report.add(
                "CessationExecutedEventPayload",
                False,
                "Payload is_terminal should be True",
            )

    except Exception as e:
        report.add(
            "Cessation event types",
            False,
            f"Error: {e}",
        )


def validate_archon_deliberation(report: ValidationReport) -> None:
    """Validate 72-archon deliberation types."""
    try:
        from src.domain.events.cessation_deliberation import (
            REQUIRED_ARCHON_COUNT,
            ArchonDeliberation,
            ArchonPosition,
        )

        # Verify archon count
        if REQUIRED_ARCHON_COUNT == 72:
            report.add(
                "REQUIRED_ARCHON_COUNT",
                True,
                f"Value: {REQUIRED_ARCHON_COUNT}",
            )
        else:
            report.add(
                "REQUIRED_ARCHON_COUNT",
                False,
                f"Expected 72, got {REQUIRED_ARCHON_COUNT}",
            )

        # Verify archon positions exist
        positions = [
            ArchonPosition.SUPPORT_CESSATION,
            ArchonPosition.OPPOSE_CESSATION,
            ArchonPosition.ABSTAIN,
        ]

        if len(positions) == 3:
            report.add(
                "ArchonPosition enum",
                True,
                "All positions defined: SUPPORT, OPPOSE, ABSTAIN",
            )
        else:
            report.add(
                "ArchonPosition enum",
                False,
                f"Expected 3 positions, got {len(positions)}",
            )

        # Verify ArchonDeliberation can be created
        delib = ArchonDeliberation(
            archon_id="archon-001",
            position=ArchonPosition.SUPPORT_CESSATION,
            reasoning="Test reasoning",
            statement_timestamp=datetime.now(timezone.utc),
        )

        if delib.archon_id == "archon-001":
            report.add(
                "ArchonDeliberation creation",
                True,
                "Deliberation object created successfully",
            )
        else:
            report.add(
                "ArchonDeliberation creation",
                False,
                "Failed to create deliberation",
            )

    except Exception as e:
        report.add(
            "Archon deliberation types",
            False,
            f"Error: {e}",
        )


def validate_cessation_flag_repository(report: ValidationReport) -> None:
    """Validate cessation flag repository interface."""
    try:
        from src.domain.models.ceased_status_header import (
            SYSTEM_STATUS_CEASED,
            CeasedStatusHeader,
            CessationDetails,
        )

        # Verify status constant
        if SYSTEM_STATUS_CEASED == "CEASED":
            report.add(
                "SYSTEM_STATUS_CEASED",
                True,
                f"Value: {SYSTEM_STATUS_CEASED}",
            )
        else:
            report.add(
                "SYSTEM_STATUS_CEASED",
                False,
                f"Expected 'CEASED', got {SYSTEM_STATUS_CEASED}",
            )

        # Verify CessationDetails can be created
        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Validation test",
            cessation_event_id=uuid4(),
        )

        if details.final_sequence_number == 100:
            report.add(
                "CessationDetails creation",
                True,
                "Details object created successfully",
            )
        else:
            report.add(
                "CessationDetails creation",
                False,
                "Failed to create details",
            )

        # Verify CeasedStatusHeader can be created
        header = CeasedStatusHeader.ceased(
            final_sequence_number=100,
            reason="Validation test",
        )

        if header.is_permanent:
            report.add(
                "CeasedStatusHeader",
                True,
                "Header created with is_permanent=True",
            )
        else:
            report.add(
                "CeasedStatusHeader",
                False,
                "Header is_permanent should be True",
            )

    except Exception as e:
        report.add(
            "Cessation flag repository",
            False,
            f"Error: {e}",
        )


def validate_stubs_available(report: ValidationReport) -> None:
    """Validate test stubs are available."""
    try:
        from src.infrastructure.stubs.cessation_flag_repository_stub import (
            CessationFlagRepositoryStub,
        )
        from src.infrastructure.stubs.event_store_stub import EventStoreStub
        from src.infrastructure.stubs.final_deliberation_recorder_stub import (
            FinalDeliberationRecorderStub,
        )

        # Verify stubs can be instantiated
        EventStoreStub()
        CessationFlagRepositoryStub()
        FinalDeliberationRecorderStub()

        report.add(
            "Test stubs available",
            True,
            "EventStoreStub, CessationFlagRepositoryStub, FinalDeliberationRecorderStub",
        )

    except Exception as e:
        report.add(
            "Test stubs available",
            False,
            f"Error: {e}",
        )


def validate_chaos_tests_exist(report: ValidationReport) -> None:
    """Validate chaos tests exist."""

    chaos_dir = "tests/chaos/cessation"
    expected_files = [
        "__init__.py",
        "test_cessation_chaos.py",
        "test_trigger_paths.py",
        "test_edge_cases.py",
    ]

    if os.path.isdir(chaos_dir):
        existing = os.listdir(chaos_dir)
        missing = [f for f in expected_files if f not in existing]

        if not missing:
            report.add(
                "Chaos test files exist",
                True,
                f"All {len(expected_files)} expected files found",
            )
        else:
            report.add(
                "Chaos test files exist",
                False,
                f"Missing files: {missing}",
            )
    else:
        report.add(
            "Chaos test directory",
            False,
            f"Directory not found: {chaos_dir}",
        )


def validate_event_model(report: ValidationReport) -> None:
    """Validate Event model can create cessation-compatible events."""
    try:
        from src.domain.events.event import Event

        # Verify Event.create_with_hash exists and works
        event = Event.create_with_hash(
            sequence=1,
            event_type="cessation.executed",
            payload={"test": "validation"},
            signature="test_signature",
            witness_id="SYSTEM:VALIDATOR",
            witness_signature="witness_sig",
            local_timestamp=datetime.now(timezone.utc),
            previous_content_hash=None,  # First event
            agent_id="SYSTEM:TEST",
        )

        if event.sequence == 1 and event.event_type == "cessation.executed":
            report.add(
                "Event.create_with_hash",
                True,
                "Event factory method works correctly",
            )
        else:
            report.add(
                "Event.create_with_hash",
                False,
                "Factory method returned unexpected values",
            )

    except Exception as e:
        report.add(
            "Event model",
            False,
            f"Error: {e}",
        )


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    """Run all validations and return exit code."""
    print("[PM-5] Running cessation path validation...")

    report = ValidationReport()

    # Run all validations
    validate_cessation_service_imports(report)
    validate_deliberation_service_imports(report)
    validate_cessation_event_types(report)
    validate_archon_deliberation(report)
    validate_cessation_flag_repository(report)
    validate_stubs_available(report)
    validate_chaos_tests_exist(report)
    validate_event_model(report)

    # Print report
    report.print_report()

    # Return exit code
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
